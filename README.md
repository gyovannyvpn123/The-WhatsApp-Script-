# WhatsApp Automation Server

Aplicație web Flask pentru automatizarea trimiterii de mesaje WhatsApp.

## Caracteristici

- Interfață web simplă pentru trimiterea de mesaje WhatsApp
- Suport pentru numere individuale sau grupuri
- Posibilitatea de a seta întârziere între mesaje
- Monitorizare în timp real a stării trimiterii
- Suport multi-utilizator

## Cerințe

- Python 3.8+
- Flask
- SQLAlchemy
- Selenium
- Chromium și ChromeDriver

## Instalare și Rulare

1. Clonați repository-ul:
```bash
git clone https://github.com/gyovannyvpn123/The-WhatsApp-Script-.git
cd The-WhatsApp-Script-
```

2. Instalați dependențele:
```bash
pip install -r render_requirements.txt
```

3. Instalați Chrome și ChromeDriver (instrucțiunile pot varia în funcție de sistemul de operare).

4. Rulați aplicația:
```bash
gunicorn --bind 0.0.0.0:5000 main:app
```

## Deploy pe Render

Acest proiect include fișierul `render.yaml` pentru Deploy to Render. Pentru a face deploy:

1. Creați un cont pe Render.com
2. Conectați repository-ul GitHub
3. Selectați opțiunea "Deploy from Render Blueprint"
4. Render va configura automat serviciul web și baza de date

## Note importante pentru WhatsApp

- Pentru utilizare în producție, trebuie să aveți un cont WhatsApp Business
- Asigurați-vă că respectați termenii de utilizare WhatsApp
- Utilizați cu responsabilitate și nu pentru spam