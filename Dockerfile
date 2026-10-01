FROM python:3.11-slim

# Empêcher la mise en tampon des sorties stdout/stderr
ENV PYTHONUNBUFFERED=1

# 1. Dépendances système & utilitaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    unzip \
    git \
    wget \
    gnupg2 \
    pkg-config \
    libssl-dev \
    libffi-dev \
    python3-dev \
    unixodbc \
    unixodbc-dev \
    && (apt-get install -y --no-install-recommends libaio1 || apt-get install -y --no-install-recommends libaio1t64) \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -f /usr/lib/x86_64-linux-gnu/libaio.so.1t64 ]; then \
         ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1; \
       fi

# 2. Pilote Microsoft ODBC pour SQL Server (AGIRH)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

# 3. Client Oracle Instant Client 19.25 (Thick mode pour Oracle 11g/11c)
WORKDIR /opt/oracle

ADD https://download.oracle.com/otn_software/linux/instantclient/1925000/instantclient-basic-linux.x64-19.25.0.0.0dbru.zip /opt/oracle/instantclient.zip

RUN unzip instantclient.zip \
    && rm instantclient.zip \
    && sh -c "echo /opt/oracle/instantclient_19_25 > /etc/ld.so.conf.d/oracle-instantclient.conf" \
    && ldconfig

ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_19_25
ENV TNS_ADMIN=/opt/oracle/instantclient_19_25/network/admin
ENV PATH=$PATH:/opt/oracle/instantclient_19_25

# 4. Installation des dépendances Python
WORKDIR /app

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copie du code applicatif
COPY . .

# 6. Point d'entrée par défaut
CMD ["python", "main.py"]
