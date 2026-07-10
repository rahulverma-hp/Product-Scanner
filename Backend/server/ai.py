from __future__ import annotations

import json
import os
import re

import requests


def _extract_first_json_object(text: str):
    """
    Best-effort extraction of the first top-level JSON object from an LLM response.
    Returns (obj_or_None, error_or_None).
    """
    if not isinstance(text, str) or not text.strip():
        return None, "Empty AI response."

    # Prefer fenced ```json blocks if present
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate), None
        except Exception:
            pass

    # Fallback: find first {...} object and attempt to parse
    start = text.find("{")
    if start == -1:
        return None, "AI response did not contain JSON."

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate), None
                    except Exception as e:
                        return None, f"Failed to parse AI JSON: {e.__class__.__name__}"
    return None, "Failed to locate complete JSON object in AI response."


def call_openrouter_chat(question, context=None):
    """
    Simple chat completion for the portfolio "Ask Me Anything" assistant.
    Returns (answer_text_or_None, error_or_None).
    """
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None, "OPENROUTER_API_KEY not set. Put it in Backend/.env (see Backend/.env.example)."

    messages = []
    if context:
        messages.append({"role": "system", "content": str(context)[:16000]})
    messages.append({"role": "user", "content": str(question)[:4000]})

    model_name = (os.environ.get("OPENROUTER_MODEL") or "deepseek/deepseek-chat").strip()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": model_name,
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 700,
            },
            timeout=45,
        )
        if response.status_code != 200:
            return None, f"AI API HTTP {response.status_code}"
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return None, "AI API returned no choices."
        text = ((choices[0] or {}).get("message") or {}).get("content")
        if not isinstance(text, str) or not text.strip():
            return None, "AI returned an empty answer."
        return text.strip(), None
    except Exception as e:
        return None, f"Error calling AI API: {e.__class__.__name__}"


def call_openrouter_ai_analysis(product, profile):
    """
    Full AI-driven product analysis. Returns (analysis_dict_or_None, error_or_None).
    Expects OPENROUTER_API_KEY (via env or Backend/.env).
    """
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None, "OPENROUTER_API_KEY not set. Put it in Backend/.env (see Backend/.env.example)."

    name = product.get("product_name", "Unknown product")
    brand = product.get("brands", "Unknown brand")
    ingredients_text = product.get("ingredients_text", "") or ""
    nutriments = product.get("nutriments", {}) or {}

    username = (profile or {}).get("display_name") or (profile or {}).get("username")
    age = (profile or {}).get("age")
    gender = (profile or {}).get("gender")
    height_cm = (profile or {}).get("height_cm")
    weight_kg = (profile or {}).get("weight_kg")

    prompt = (
        "You are a careful, neutral nutrition assistant. "
        "Analyze the product for THIS specific user profile. "
        "Return ONLY valid JSON (no markdown). "
        "Be concrete and explain strange ingredient names in simple terms.\n\n"
        "JSON schema (return exactly these keys):\n"
        "{\n"
        '  \"overall_score\": {\"score\": 0-100, \"label\": \"Good|Okay|Bad\", \"one_line\": \"...\"},\n'
        '  \"sections\": {\n'
        '    \"ingredients\": {\n'
        '      \"good\": [{\"name\": \"...\", \"why\": \"...\"}],\n'
        '      \"bad\":  [{\"name\": \"...\", \"why\": \"...\", \"risk_level\": \"low|medium|high\"}],\n'
        '      \"neutral_or_unknown\": [{\"name\": \"...\", \"what_it_is\": \"...\"}]\n'
        "    },\n"
        '    \"nutrition\": {\n'
        '      \"high\": [{\"nutrient\": \"sugar|salt|fat|saturated fat|calories|...\", \"why\": \"...\"}],\n'
        '      \"good\": [{\"nutrient\": \"fiber|protein|...\", \"why\": \"...\"}],\n'
        '      \"notes\": [\"...\"]\n'
        "    },\n"
        '    \"profile_advice\": {\n'
        '      \"for_user\": \"...\",\n'
        '      \"recommended_max_per_day\": \"...\",\n'
        '      \"watch_out_for\": [\"...\"]\n'
        "    }\n"
        "  },\n"
        '  \"disclaimer\": \"...\"\n'
        "}\n\n"
        "Rules:\n"
        "- If you are uncertain about an ingredient, put it in neutral_or_unknown.\n"
        "- Prefer short, easy sentences; no medical diagnoses.\n"
        "- Tailor advice to age, gender, weight, and goals implied (general health).\n\n"
        f"Product name: {name}\n"
        f"Brand: {brand}\n"
        f"Ingredients text: {ingredients_text}\n"
        f"Nutriments per 100 g (raw JSON): {nutriments}\n\n"
        f"User profile: username={username}, age={age}, gender={gender}, height_cm={height_cm}, weight_kg={weight_kg}\n"
    )

    def _do_call(prompt_text: str):
        model_name = (os.environ.get("OPENROUTER_MODEL") or "deepseek/deepseek-chat").strip()
        http_referer = (os.environ.get("OPENROUTER_HTTP_REFERER") or "").strip()
        title = (os.environ.get("OPENROUTER_TITLE") or "").strip()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if http_referer:
            headers["HTTP-Referer"] = http_referer
        if title:
            headers["X-OpenRouter-Title"] = title
        return requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.4,
                "max_tokens": 1200,
            },
            timeout=45,
        )

    def _parse_candidate_text(resp_json):
        choices = resp_json.get("choices") or []
        if not choices:
            return None, "AI API returned no choices."
        msg = (choices[0] or {}).get("message") or {}
        text = msg.get("content")
        if not isinstance(text, str):
            return None, "AI API response format unexpected (no message.content)."
        return text, None

    def _parse_response(resp_json):
        text, t_err = _parse_candidate_text(resp_json)
        if t_err:
            return None, t_err

        obj, perr = _extract_first_json_object(text)
        if perr:
            # One-shot repair: ask model to output VALID JSON only.
            repair_prompt = (
                "Fix this into valid JSON matching the exact schema. "
                "Return ONLY JSON (no markdown, no extra text).\n\n"
                f"BAD_OUTPUT:\n{text[:12000]}"
            )
            r2 = _do_call(repair_prompt)
            if r2.status_code == 200:
                data2 = r2.json()
                text2, t_err2 = _parse_candidate_text(data2)
                if not t_err2:
                    obj2, perr2 = _extract_first_json_object(text2)
                    if not perr2 and isinstance(obj2, dict):
                        return obj2, None
            return None, perr
        if not isinstance(obj, dict):
            return None, "AI JSON was not an object."
        return obj, None

    try:
        response = _do_call(prompt)
        if response.status_code != 200:
            msg = f"AI API HTTP {response.status_code}"
            try:
                body = response.json()
                err = body.get("error") or body
                if isinstance(err, dict):
                    detail = err.get("message") or err.get("code")
                elif isinstance(err, str):
                    detail = err
                else:
                    detail = None
                if detail:
                    msg += f": {detail}"
            except Exception:
                pass
            return None, msg

        data = response.json()
        return _parse_response(data)
    except Exception as e:
        return None, f"Error calling AI API: {e.__class__.__name__}"

