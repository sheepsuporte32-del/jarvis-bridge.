"""Alexa custom-skill Lambda starter. Configure JARVIS_BRIDGE_URL and JARVIS_API_KEY as Lambda env vars.
Use the Alexa Skills Kit SDK to verify incoming Alexa requests before enabling this handler in production.
"""
import json
import os
import uuid
import urllib.request

BRIDGE_URL = os.environ.get("JARVIS_BRIDGE_URL", "").rstrip("/")
API_KEY = os.environ.get("JARVIS_API_KEY", "")


def _alexa_response(text, should_end=True):
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {"type": "PlainText", "text": text},
            "shouldEndSession": should_end,
        },
    }


def lambda_handler(event, context):
    # This is a starter handler. Production deployment MUST validate the Alexa request signature
    # and application ID using the Alexa Skills Kit SDK or an equivalent official verifier.
    req = event.get("request", {})
    req_type = req.get("type")
    if req_type == "LaunchRequest":
        return _alexa_response("JARVIS conectado. Você pode dizer: abrir WhatsApp.")
    if req_type == "IntentRequest":
        intent = req.get("intent", {}).get("name", "")
        if intent in ("OpenWhatsAppIntent", "AMAZON.HelpIntent"):
            if intent == "AMAZON.HelpIntent":
                return _alexa_response("Diga: abrir WhatsApp.")
            if not BRIDGE_URL or not API_KEY:
                return _alexa_response("A ponte do JARVIS ainda não está configurada.")
            body = json.dumps({"action": "open_whatsapp", "confirmation": True,
                               "request_id": "alexa-" + str(uuid.uuid4())}).encode()
            request = urllib.request.Request(
                BRIDGE_URL + "/v1/actions/execute", data=body, method="POST",
                headers={"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=8) as response:
                    if response.status == 200:
                        return _alexa_response("Enviei o comando para o celular. Confirme se o WhatsApp abriu.")
            except Exception:
                pass
            return _alexa_response("Não consegui enviar o comando. Verifique a conexão do JARVIS.")
        if intent == "AMAZON.StopIntent" or intent == "AMAZON.CancelIntent":
            return _alexa_response("Até logo.")
    return _alexa_response("Não entendi. Diga: abrir WhatsApp.")
