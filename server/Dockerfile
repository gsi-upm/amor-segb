FROM python:3.10-alpine

LABEL org.opencontainers.image.source=https://github.com/gsi-upm/amor-segb
LABEL org.opencontainers.image.description="AMOR-SEGB server"
LABEL org.opencontainers.image.authors="Grupo de Sistemas Inteligentes - Universidad Politécnica de Madrid"
LABEL org.opencontainers.image.documentation="https://amor-segb.readthedocs.io/"
LABEL org.opencontainers.image.licenses=MIT

COPY requirements.txt requirements.txt
RUN apk add --no-cache gcc musl-dev linux-headers
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

ENV FLASK_APP=/app/app.py
ENV FLASK_RUN_HOST=0.0.0.0
EXPOSE 5000

CMD ["flask", "run", "--debug"]