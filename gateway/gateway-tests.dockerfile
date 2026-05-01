FROM python:3.12-slim

WORKDIR /tests

COPY tests/integration/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY tests/integration/ .

CMD ["pytest","-q","--junitxml=/reports/junit.xml","--html=/reports/report.html","--self-contained-html"]
