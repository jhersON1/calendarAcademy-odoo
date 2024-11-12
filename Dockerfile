FROM odoo:latest

USER root

RUN pip3 install --break-system-packages --ignore-installed openai

USER odoo