from __future__ import annotations

import os
import sqlite3

from flask import Flask, jsonify, render_template, request

from Backend.lifeve.enrichment import enrich_product
from Backend.lifeve.advice_lora import call_lora_advice
from Backend.lifeve.classifier import HealthClassifier
from Backend.lifeve.features import extract_feature_row
from Backend.lifeve.health_engine import build_advice_text, evaluate_health

from .ai import call_assistant_chat, call_openrouter_ai_analysis
from .auth import (
    auth_token_from_request,
    create_session,
    get_profile_by_token,
    hash_password,
    verify_password,
)
from .db import get_db_connection
from Backend.lifeve.hf_vision import extract_ingredients_from_image, extract_nutrition_from_image
from .products import (
    fetch_foodrepo_off_product,
    fetch_local_product_off_shape,
    fetch_openfoodfacts_product,
    fetch_sample_catalog_product,
)

_health_classifier = HealthClassifier.load()


def _lora_runtime_enabled() -> bool:
    return os.getenv("LORA_ADVICE_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def register_routes(app: Flask) -> None:
    @app.route("/")
    def home():
        return render_template("front.html")

    @app.route("/scan-ui")
    def scan_ui():
        return render_template("index.html")

    @app.route("/auth/register", methods=["POST"])
    def auth_register():
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        display_name = (data.get("display_name") or "").strip() or None
        password = data.get("password") or ""

        age = data.get("age")
        gender = (data.get("gender") or "").lower()
        height_cm = data.get("height_cm")
        weight_kg = data.get("weight_kg")

        if not username or len(username) < 3:
            return jsonify({"error": "Username is required (min 3 chars)."}), 400
        if not password or len(password) < 6:
            return jsonify({"error": "Password is required (min 6 chars)."}), 400

        if (
            age is None
            or gender not in ("male", "female")
            or height_cm is None
            or weight_kg is None
        ):
            return (
                jsonify(
                    {
                        "error": "age, gender (male/female), height_cm and weight_kg are required"
                    }
                ),
                400,
            )

        conn = get_db_connection()
        try:
            cur = conn.execute(
                """
                INSERT INTO profiles (username, display_name, password_hash, age, gender, height_cm, weight_kg)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    display_name,
                    hash_password(password),
                    int(age),
                    gender,
                    float(height_cm),
                    float(weight_kg),
                ),
            )
            profile_id = cur.lastrowid
            token = create_session(conn, profile_id)
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            return jsonify({"error": "That username is already taken."}), 409

        profile = conn.execute(
            "SELECT id, username, display_name, age, gender, height_cm, weight_kg FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        conn.close()
        return jsonify({"token": token, "profile": dict(profile)}), 201

    @app.route("/auth/login", methods=["POST"])
    def auth_login():
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify({"error": "Username and password are required."}), 400

        conn = get_db_connection()
        row = conn.execute(
            "SELECT id, password_hash FROM profiles WHERE LOWER(username) = LOWER(?)",
            (username,),
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Invalid username or password."}), 401

        if not verify_password(password, row["password_hash"]):
            conn.close()
            return jsonify({"error": "Invalid username or password."}), 401

        token = create_session(conn, row["id"])
        conn.commit()
        profile = conn.execute(
            "SELECT id, username, display_name, age, gender, height_cm, weight_kg FROM profiles WHERE id = ?",
            (row["id"],),
        ).fetchone()
        conn.close()
        return jsonify({"token": token, "profile": dict(profile)}), 200

    @app.route("/me", methods=["GET"])
    def me():
        token = auth_token_from_request()
        conn = get_db_connection()
        profile = get_profile_by_token(conn, token)
        conn.close()
        if not profile:
            return jsonify({"error": "Not authenticated."}), 401
        return jsonify({"profile": profile}), 200

    @app.route("/me", methods=["DELETE"])
    def delete_me():
        token = auth_token_from_request()
        if not token:
            return jsonify({"error": "Not authenticated."}), 401
        conn = get_db_connection()
        profile = get_profile_by_token(conn, token)
        if not profile:
            conn.close()
            return jsonify({"error": "Not authenticated."}), 401
        pid = profile.get("id")
        try:
            # Delete all sessions for this user first, then the profile.
            conn.execute("DELETE FROM sessions WHERE profile_id = ?", (pid,))
            conn.execute("DELETE FROM profiles WHERE id = ?", (pid,))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True}), 200

    @app.route("/ask", methods=["POST"])
    def ask():
        """Portfolio 'Ask Me Anything' assistant — proxies to OpenRouter server-side."""
        data = request.get_json() or {}
        question = (data.get("question") or "").strip()
        context = data.get("context") or ""
        if not question:
            return jsonify({"error": "Question is required."}), 400
        if len(question) > 2000:
            return jsonify({"error": "Question is too long."}), 400

        answer, error = call_assistant_chat(question, context=context)
        if error:
            return jsonify({"error": error}), 502
        return jsonify({"answer": answer}), 200

    @app.route("/scan", methods=["POST"])
    def scan():
        try:
            return _handle_scan()
        except Exception as exc:
            return jsonify({"error": f"Scan failed: {exc.__class__.__name__}: {exc}"}), 500

    @app.route("/scan/package-photo", methods=["POST"])
    def scan_package_photo():
        """Season 2: extract ingredients/nutrition from a packaging photo (HF vision models)."""
        try:
            image = request.files.get("image")
            if image is None or not image.filename:
                return jsonify({"error": "Upload an image file as multipart field 'image'."}), 400

            mode = (request.form.get("mode") or "ingredients").strip().lower()
            if mode == "nutrition":
                result = extract_nutrition_from_image(image)
            else:
                result = extract_ingredients_from_image(image)

            barcode = (request.form.get("barcode") or "").strip()
            if barcode and result.get("ingredients_text"):
                return _handle_scan_with_product_override(
                    barcode=barcode,
                    ingredients_text=result["ingredients_text"],
                    package_scan=result,
                )

            return jsonify({"package_scan": result}), 200
        except Exception as exc:
            return jsonify({"error": f"Package scan failed: {exc.__class__.__name__}: {exc}"}), 500


def _handle_scan():
    data = request.get_json() or {}
    barcode = data.get("barcode")
    token = auth_token_from_request()

    if not barcode:
        return jsonify({"error": "No barcode received"}), 400

    conn = get_db_connection()
    effective_profile = get_profile_by_token(conn, token)
    conn.close()

    if token and not effective_profile:
        return jsonify({"error": "Not authenticated."}), 401

    product = None
    data_source = None

    off_product, off_error = fetch_openfoodfacts_product(barcode)
    if off_product:
        product = off_product
        data_source = "openfoodfacts"
    else:
        fr_product = fetch_foodrepo_off_product(barcode)
        if fr_product:
            product = fr_product
            data_source = "foodrepo"
        else:
            local_product = fetch_local_product_off_shape(barcode)
            if local_product:
                product = local_product
                data_source = "local"
            else:
                sample_product = fetch_sample_catalog_product(barcode)
                if sample_product:
                    product = sample_product
                    data_source = "sample_catalog"

    if not product:
        msg = "Could not fetch product data."
        if off_error:
            msg += f" OpenFoodFacts: {off_error}."
        if not (os.environ.get("FOODREPO_API_KEY") or "").strip():
            msg += (
                " Set environment variable FOODREPO_API_KEY (from foodrepo.org) "
                "to also search Open Food Repo as a backup."
            )
        else:
            msg += " Not found in Open Food Repo either."
        msg += " Try a sample barcode like 3017620422003 (Nutella) or add an entry to Backend/products.json."
        return jsonify({"error": msg}), 404

    name = product.get("product_name", "Unknown product")
    brand = product.get("brands", "Unknown brand")
    ingredients = product.get("ingredients_text", "No ingredient info available")

    product, hf_insights = enrich_product(product)
    health = evaluate_health(product, profile=effective_profile, hf_insights=hf_insights)

    ml_prediction = None
    ml_prediction_error = None
    if _health_classifier is not None:
        try:
            feature_row = extract_feature_row(product, profile=effective_profile, health=health)
            ml_prediction = _health_classifier.predict(feature_row)
        except Exception as exc:
            ml_prediction_error = f"{exc.__class__.__name__}: {exc}"

    ai_analysis, ai_analysis_error = call_openrouter_ai_analysis(product, effective_profile)

    lora_advice = None
    lora_advice_error = None
    if _lora_runtime_enabled():
        lora_advice, lora_advice_error = call_lora_advice(
            product, effective_profile, health=health
        )

    personalised = {
        "personalised_summary": build_advice_text(health),
        "source": "rules",
        "disclaimer": "General food guidance only — not medical advice.",
    }
    if lora_advice and lora_advice.get("personalised_summary"):
        personalised = lora_advice

    payload = {
        "product_name": name,
        "brand": brand,
        "ingredients": ingredients,
        "health": health,
        "hf_insights": hf_insights or None,
        "ml_prediction": ml_prediction,
        "ml_prediction_error": ml_prediction_error,
        "personalised": personalised,
        "ai_analysis": ai_analysis,
        "ai_analysis_error": ai_analysis_error,
        "profile": effective_profile,
        "data_source": data_source,
    }
    if _lora_runtime_enabled():
        payload["lora_advice"] = lora_advice
        payload["lora_advice_error"] = lora_advice_error

    return jsonify(payload)


def _handle_scan_with_product_override(
    *,
    barcode: str,
    ingredients_text: str,
    package_scan: dict,
):
    token = auth_token_from_request()
    conn = get_db_connection()
    effective_profile = get_profile_by_token(conn, token)
    conn.close()

    if token and not effective_profile:
        return jsonify({"error": "Not authenticated."}), 401

    product = None
    data_source = None
    off_product, _ = fetch_openfoodfacts_product(barcode)
    if off_product:
        product = off_product
        data_source = "openfoodfacts"
    else:
        sample_product = fetch_sample_catalog_product(barcode)
        if sample_product:
            product = sample_product
            data_source = "sample_catalog"

    if not product:
        product = {
            "code": barcode,
            "product_name": f"Product {barcode}",
            "brands": "Unknown brand",
            "ingredients_text": ingredients_text,
            "nutriments": {},
        }
        data_source = "package_photo"
    else:
        product = dict(product)
        product["ingredients_text"] = ingredients_text
        data_source = f"{data_source}+package_photo"

    product, hf_insights = enrich_product(product)
    health = evaluate_health(product, profile=effective_profile, hf_insights=hf_insights)

    ml_prediction = None
    if _health_classifier is not None:
        try:
            feature_row = extract_feature_row(product, profile=effective_profile, health=health)
            ml_prediction = _health_classifier.predict(feature_row)
        except Exception:
            pass

    ai_analysis, ai_analysis_error = call_openrouter_ai_analysis(product, effective_profile)

    return jsonify({
        "product_name": product.get("product_name"),
        "brand": product.get("brands"),
        "ingredients": ingredients_text,
        "health": health,
        "hf_insights": hf_insights or None,
        "ml_prediction": ml_prediction,
        "ai_analysis": ai_analysis,
        "ai_analysis_error": ai_analysis_error,
        "package_scan": package_scan,
        "profile": effective_profile,
        "data_source": data_source,
    })

