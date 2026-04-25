from __future__ import annotations

import os
import sqlite3

from flask import Flask, jsonify, render_template, request

from .ai import call_openrouter_ai_analysis
from .auth import (
    auth_token_from_request,
    create_session,
    get_profile_by_token,
    hash_password,
    verify_password,
)
from .db import get_db_connection
from .products import (
    fetch_foodrepo_off_product,
    fetch_local_product_off_shape,
    fetch_openfoodfacts_product,
)


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

    @app.route("/scan", methods=["POST"])
    def scan():
        data = request.get_json() or {}
        barcode = data.get("barcode")
        token = auth_token_from_request()

        if not barcode:
            return jsonify({"error": "No barcode received"})

        conn = get_db_connection()
        effective_profile = get_profile_by_token(conn, token)
        conn.close()

        # Allow guest usage: when no token is provided, proceed with a generic analysis.
        # If a token is provided but invalid, treat it as an auth error.
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
            msg += " You can also add a barcode entry to Backend/products.json for offline testing."
            return jsonify({"error": msg})

        name = product.get("product_name", "Unknown product")
        brand = product.get("brands", "Unknown brand")
        ingredients = product.get("ingredients_text", "No ingredient info available")
        ai_analysis, ai_analysis_error = call_openrouter_ai_analysis(product, effective_profile)
        if ai_analysis_error:
            return jsonify({"error": ai_analysis_error}), 502

        return jsonify(
            {
                "product_name": name,
                "brand": brand,
                "ingredients": ingredients,
                "ai_analysis": ai_analysis,
                "profile": effective_profile,
                "data_source": data_source,
            }
        )

