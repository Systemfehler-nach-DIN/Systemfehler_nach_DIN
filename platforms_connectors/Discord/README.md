# Discord-Connector

Dieser Connector ist API-first, fail-closed und standardmäßig im `DRY_RUN`-Modus.

## Status

Der Adapter wird in der nächsten Implementierungswelle gegen die offizielle Discord-API verdrahtet. Bis dahin sind keine Live-Aktionen freigeschaltet.

## Sicherheitsgrenzen

- Keine Tokens, Cookies oder Secrets im Repository.
- Live-Publishing benötigt explizite Plattformfreigabe und bleibt standardmäßig deaktiviert.
- Browser-Automation ist kein stiller Fallback für eine offizielle API.
- Jede Veröffentlichung muss anhand der API-Antwort unabhängig verifiziert und idempotent behandelt werden.
