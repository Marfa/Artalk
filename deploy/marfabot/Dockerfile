FROM python:3.12-alpine

WORKDIR /app
COPY artalk_api.py ban.py format.py telegram_api.py main.py self_check.py ./

RUN python3 self_check.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8086
CMD ["python3", "main.py"]
