up:        ; docker compose up -d --build
down:      ; docker compose down
logs:      ; docker compose logs -f app
load:      ; python3 scripts/load_test.py 20   # Needs: pip install pillow
dashboard: ; python3 scripts/gen_dashboard.py && docker compose restart grafana
