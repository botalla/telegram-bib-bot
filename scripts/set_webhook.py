"""Script CLI d'administration et configuration du Webhook Telegram.

Permet d'enregistrer, d'inspecter ou de supprimer l'URL de Webhook Telegram.

Exemples d'utilisation :
  python scripts/set_webhook.py --set https://biblio-bot-xxx.a.run.app/webhook --secret MON_SECRET
  python scripts/set_webhook.py --info
  python scripts/set_webhook.py --delete
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def get_bot_token() -> str:
    """Récupère le jeton Telegram depuis l'environnement ou les arguments."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token and os.path.exists(".env"):
        with open(".env", encoding="utf-8") as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not token:
        print("❌ Erreur : Variable TELEGRAM_BOT_TOKEN non trouvée (définissez-la ou fournissez un fichier .env).")
        sys.exit(1)
    return token


def make_telegram_request(token: str, method: str, payload: dict | None = None) -> dict:
    """Effectue un appel HTTPS vers l'API Telegram Bot."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8") if payload else None

    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload else "GET")

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            return json.loads(err_msg)
        except json.JSONDecodeError:
            return {"ok": False, "description": err_msg}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "description": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Gestion du Webhook Telegram pour BiblioBot Paris.")
    parser.add_argument("--set", dest="webhook_url", help="URL publique HTTPS du webhook (ex: https://.../webhook)")
    parser.add_argument("--secret", dest="secret_token", help="Secret token d'authentification pour le webhook")
    parser.add_argument("--info", action="store_true", help="Affiche les informations actuelles du Webhook")
    parser.add_argument("--delete", action="store_true", help="Supprime le Webhook actuel (repasse en mode getUpdates)")
    parser.add_argument("--token", dest="token", help="Token du bot Telegram (optionnel, sinon lit TELEGRAM_BOT_TOKEN)")

    args = parser.parse_args()
    token = args.token or get_bot_token()

    if args.info:
        print("🔍 Récupération des informations du Webhook...")
        res = make_telegram_request(token, "getWebhookInfo")
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.delete:
        print("🗑️ Suppression du Webhook...")
        res = make_telegram_request(token, "deleteWebhook", {"drop_pending_updates": False})
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.webhook_url:
        payload = {
            "url": args.webhook_url,
            "drop_pending_updates": False,
            "allowed_updates": ["message", "callback_query"],
        }
        if args.secret_token:
            payload["secret_token"] = args.secret_token
        elif "TELEGRAM_WEBHOOK_SECRET" in os.environ:
            payload["secret_token"] = os.environ["TELEGRAM_WEBHOOK_SECRET"]

        print(f"🚀 Enregistrement du Webhook sur : {args.webhook_url}...")
        res = make_telegram_request(token, "setWebhook", payload)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        if res.get("ok"):
            print("✅ Webhook configuré avec succès !")
        else:
            print("❌ Échec de configuration du Webhook.")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
