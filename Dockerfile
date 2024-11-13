FROM odoo:latest

USER root

RUN pip3 install --break-system-packages --ignore-installed openai

RUN pip3 install --break-system-packages firebase-admin

USER odoo