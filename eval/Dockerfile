# rahbar-eval: the Part B suite and the release gate as a Job (architecture-a3 9.2). Built from a staging
# directory by `make eval-image` (eval/ plus scripts/trace_*.py), so the build context stays small.
FROM python:3.12-slim-bookworm
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
RUN pip install --no-cache-dir httpx==0.28.1 PyYAML==6.0.2 \
 && groupadd -g 10001 app && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin app
WORKDIR /app
COPY eval/ eval/
COPY scripts/ scripts/
USER 10001:10001
CMD ["python", "-m", "eval.suite.job"]
