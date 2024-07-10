import os

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent.parent / "templates"),
    autoescape=True,
)

nginx_template = templates.get_template("nginx.template.conf")

variables = {
    "upstream_name": "webapp",
    "upstream_service": "literev",  # django container hostname
    "upstream_port": os.environ.get("FRONTEND_HOST_PORT"),
    "certbot_root": "/var/www/certbot",
    "letsencrypt_root": "/etc/letsencrypt",
    "domain": os.environ.get("CERTBOT_DOMAIN").split(",")[0],  # Prevents www.
}

output = nginx_template.render(variables)

nginx_dir = Path(__file__).parent.parent / "data" / "config" / "prod"

nginx_dir.mkdir(parents=True, exist_ok=True)

file = nginx_dir / "prod.nginx.conf"

file.touch()

with open(file, "w") as f:
    f.write(output)
