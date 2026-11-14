FROM python:3.14.8-slim-trixie@sha256:9b629e83e1a517e01eaf7a36362563c0c7f620d3e4747f7dcf79564e290b7b48

# O firewall do runner permite HTTPS. systemctl é usado com --root nos testes.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git nodejs systemd unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSLo /tmp/terraform.zip https://releases.hashicorp.com/terraform/1.15.9/terraform_1.15.9_linux_amd64.zip \
    && echo '76edd0b22d2f27d3d2e097cd793209646f719cf60f02ff3af626b07361137da1  /tmp/terraform.zip' | sha256sum -c - \
    && unzip /tmp/terraform.zip terraform -d /usr/local/bin \
    && rm /tmp/terraform.zip

RUN pip install --no-cache-dir 'ansible==14.5.0' 'ansible-core==2.21.5' 'PyYAML==6.0.3' 'Jinja2==3.1.6' \
    && ansible-galaxy collection install 'artis3n.tailscale:==1.2.1' --no-deps -p /usr/share/ansible/collections
