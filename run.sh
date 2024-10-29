sh dev.sh makemigrations
sh dev.sh migrate
uvicorn base.asgi:application --port 8000 --host 0.0.0.0 --workers $(($(awk '/^processor/{n+=1}END{print n}' /proc/cpuinfo)*$1+1)) --lifespan off --log-level debug