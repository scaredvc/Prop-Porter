FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./src /app/src
COPY player_points_predictor.pkl .
COPY .env .
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "src.api:app"]
