@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python -c "import app48; from app49 import catalogo_bp; import app51; import app53; import app55; import app57; import app61; import app63; import app64; import app65; import app66; import app67; import app88; import app93; import app95; import app110; import app117; import app122; import app129; import app131; import app142; import app145; import app152; import app155; import app156; import app157; import app158; import app159; import app160; import app163; import app165; app48.app.register_blueprint(catalogo_bp); import app182; app48.app.run(host='127.0.0.1', port=5000, debug=True)"
pause
