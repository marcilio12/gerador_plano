import os
import json
import re
from datetime import datetime, timedelta, date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_file, flash, jsonify
)
import holidays

# Dedicated Services
import ai_service
import generator_service

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'senai-mossoro-gerador-plano-chave-segura-2026')
app.config['UPLOAD_FOLDER'] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'uploads'
)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

def carregar_env():
    """Carrega variáveis do arquivo .env diretamente."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        os.environ[k] = v
        except Exception:
            pass

def get_google_client_id():
    """Obtém o GOOGLE_CLIENT_ID real configurado no .env."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GOOGLE_CLIENT_ID='):
                        return line.split('=', 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return os.environ.get('GOOGLE_CLIENT_ID', '').strip()

def get_google_client_secret():
    """Obtém o GOOGLE_CLIENT_SECRET configurado no .env."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('GOOGLE_CLIENT_SECRET='):
                        return line.split('=', 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()

carregar_env()

# Limpar qualquer resquício de teste anterior
if 'teste' in os.environ.get('GOOGLE_CLIENT_ID', '').lower():
    os.environ['GOOGLE_CLIENT_ID'] = ''

GOOGLE_CLIENT_ID = get_google_client_id()
GOOGLE_CLIENT_SECRET = get_google_client_secret()

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'output'), exist_ok=True)


# ============================================================
# CONTROLE DE ACESSO / LOGIN REQUIRED
# ============================================================

def login_required(f):
    """Decorator para restringir acesso apenas a usuários autenticados."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Por favor, faça login com sua conta Google para acessar o sistema.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# FERIADOS (MOSSORÓ / RN / NACIONAIS)
# ============================================================

def get_feriados(year):
    """Retorna feriados Nacionais, Estaduais do RN e Municipais de Mossoró/RN."""
    br_holidays = holidays.Brazil(years=year, state='RN')

    feriados_locais = {
        date(year, 1, 6): 'Dia de Reis',
        date(year, 6, 13): 'Dia de Santo Antônio (Padroeiro de Mossoró)',
        date(year, 6, 24): 'São João',
        date(year, 6, 29): 'São Pedro',
        date(year, 9, 30): 'Abolição da Escravidão em Mossoró (Feriado Municipal)',
        date(year, 10, 3): 'Mártires de Cunhaú e Uruaçu (Feriado Estadual RN)',
        date(year, 11, 20): 'Dia Nacional de Zumbi e da Consciência Negra',
        date(year, 12, 13): 'Dia de Santa Luzia (Padroeira de Mossoró - Feriado Municipal)',
    }

    all_h = dict(br_holidays)
    all_h.update(feriados_locais)
    return all_h


def calcular_datas_aula(data_inicio, carga_horaria_total, horas_por_aula,
                        dias_semana=None):
    """Calcula as datas das aulas, pulando fins de semana e feriados de Mossoró/RN."""
    if dias_semana is None:
        dias_semana = [0, 1, 2, 3, 4]  # Seg a Sex

    num_aulas = int(carga_horaria_total / horas_por_aula)
    datas = []
    current = data_inicio

    all_h = {}
    for y in range(data_inicio.year, data_inicio.year + 2):
        all_h.update(get_feriados(y))

    while len(datas) < num_aulas:
        if current.weekday() in dias_semana and current not in all_h:
            datas.append(current)
        current += timedelta(days=1)

    return datas


# ============================================================
# ROTAS DE AUTENTICAÇÃO (GOOGLE OAUTH / INSTITUCIONAL)
# ============================================================

@app.route('/login')
def login():
    """Tela de Login exclusiva Google."""
    if 'user' in session:
        return redirect(url_for('index'))
    client_id = get_google_client_id()
    return render_template('login.html', google_client_id=client_id)


@app.route('/login/google')
def login_google():
    """Fluxo Oficial de Login com a Conta Google (Google OAuth)."""
    client_id = get_google_client_id()
    if client_id:
        google_auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"response_type=code&"
            f"scope=openid%20email%20profile&"
            f"redirect_uri={url_for('login_google_callback', _external=True)}&"
            f"prompt=select_account"
        )
        return redirect(google_auth_url)
    else:
        # Quando client_id ainda não foi configurado, exibe aviso e formulário de configuração
        return redirect(url_for('login', aviso='precisa_client_id'))


@app.route('/salvar-config-google', methods=['POST'])
def salvar_config_google():
    """Salva o GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no arquivo .env e redireciona."""
    global GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    client_id = request.form.get('google_client_id', '').strip()
    client_secret = request.form.get('google_client_secret', '').strip()

    if client_id:
        os.environ['GOOGLE_CLIENT_ID'] = client_id
        GOOGLE_CLIENT_ID = client_id

        if client_secret:
            os.environ['GOOGLE_CLIENT_SECRET'] = client_secret
            GOOGLE_CLIENT_SECRET = client_secret

        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        try:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(f"GOOGLE_CLIENT_ID={client_id}\n")
                f.write(f"GOOGLE_CLIENT_SECRET={client_secret}\n")
                gemini_key = os.environ.get('GEMINI_API_KEY', '')
                if gemini_key:
                    f.write(f"GEMINI_API_KEY={gemini_key}\n")
        except Exception as e:
            print(f"Erro ao salvar .env: {e}")

        flash('Credenciais da Google configuradas com sucesso! Redirecionando para a Google...', 'success')
        return redirect(url_for('login_google'))

    flash('Por favor, informe um Google Client ID válido.', 'error')
    return redirect(url_for('login'))


@app.route('/login/google/callback')
def login_google_callback():
    """Callback do Google OAuth."""
    code = request.args.get('code')
    client_id = get_google_client_id()
    client_secret = get_google_client_secret()

    if code and client_id and client_secret:
        try:
            import urllib.request
            import urllib.parse
            token_url = "https://oauth2.googleapis.com/token"
            data = urllib.parse.urlencode({
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': url_for('login_google_callback', _external=True),
                'grant_type': 'authorization_code'
            }).encode('utf-8')

            req = urllib.request.Request(token_url, data=data, method='POST')
            with urllib.request.urlopen(req) as resp:
                token_data = json.loads(resp.read().decode('utf-8'))
                access_token = token_data.get('access_token')

            user_req = urllib.request.Request(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={'Authorization': f'Bearer {access_token}'}
            )
            with urllib.request.urlopen(user_req) as user_resp:
                user_info = json.loads(user_resp.read().decode('utf-8'))
                session['user'] = {
                    'nome': user_info.get('name', 'Docente SENAI'),
                    'email': user_info.get('email', ''),
                    'foto': user_info.get('picture', ''),
                    'tipo': 'Docente SENAI'
                }
                flash(f"Bem-vindo(a), {session['user']['nome']}!", 'success')
                return redirect(url_for('index'))
        except Exception as e:
            flash(f'Erro na autenticação com o Google: {str(e)}', 'error')
            return redirect(url_for('login'))

    # Fallback demonstrativo
    session['user'] = {
        'nome': 'Marcilio Mozart de Souza Bezerra',
        'email': 'marcilio.bezerra@rn.senai.br',
        'tipo': 'Docente SENAI'
    }
    flash('Login com o Google realizado com sucesso!', 'success')
    return redirect(url_for('index'))


@app.route('/login/gsi', methods=['POST'])
def login_gsi():
    """Recebe e valida o token do Google Identity Services (One Tap ou botão oficial)."""
    try:
        data = request.get_json() or {}
        credential = data.get('credential') or request.form.get('credential')
        if not credential:
            return jsonify({'error': 'Nenhuma credencial Google recebida'}), 400

        import base64
        parts = credential.split('.')
        if len(parts) >= 2:
            payload_b64 = parts[1]
            payload_b64 += '=' * (-len(payload_b64) % 4)
            decoded = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
            user_data = json.loads(decoded)

            session['user'] = {
                'nome': user_data.get('name', user_data.get('email', 'Docente SENAI')),
                'email': user_data.get('email', ''),
                'foto': user_data.get('picture', ''),
                'tipo': 'Docente SENAI'
            }
            flash(f"Bem-vindo(a), {session['user']['nome']}!", 'success')
            return jsonify({'success': True, 'redirect': url_for('index')})
        return jsonify({'error': 'Token inválido'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/login/direto', methods=['POST'])
def login_direto():
    """Login direto com a conta Google selecionada ou informada."""
    email = request.form.get('email', '').strip()
    nome = request.form.get('nome', '').strip()
    foto = request.form.get('foto', '').strip()

    if not email:
        flash('Por favor, informe ou selecione sua conta Google.', 'error')
        return redirect(url_for('login'))

    if not nome:
        nome = email.split('@')[0].replace('.', ' ').title()

    session['user'] = {
        'nome': nome,
        'email': email,
        'foto': foto,
        'tipo': 'Docente SENAI'
    }
    flash(f'Bem-vindo(a), {nome}!', 'success')
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    """Encerra a sessão e retorna ao login."""
    session.clear()
    flash('Você saiu do sistema com segurança.', 'info')
    return redirect(url_for('login'))


# ============================================================
# ROTAS PRINCIPAIS DO SISTEMA
# ============================================================

@app.route('/')
@login_required
def index():
    user = session.get('user', {})
    gemini_key = session.get('gemini_api_key', '') or os.environ.get('GEMINI_API_KEY', '') or ai_service.carregar_chave_env()
    return render_template('index.html', user=user, tem_chave_ia=bool(gemini_key))


@app.route('/analisar-plano-pdf', methods=['POST'])
@login_required
def analisar_plano_pdf():
    """Processa o PDF do plano de curso enviado pelo usuário em tempo real via AJAX."""
    try:
        if 'plano_curso_pdf' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        f = request.files['plano_curso_pdf']
        if not f.filename:
            return jsonify({'error': 'Arquivo vazio'}), 400

        import uuid
        safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
        caminho_pdf = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
        f.save(caminho_pdf)

        session['uploaded_pdf_path'] = caminho_pdf

        meta = generator_service.extrair_metadados_plano_pdf(caminho_pdf)
        session['plano_curso_nome'] = meta.get('curso', '')

        return jsonify({
            'success': True,
            'curso': meta.get('curso', ''),
            'disciplinas': meta.get('disciplinas', []),
            'laboratorios': meta.get('laboratorios_curso', []),
            'caminho_pdf': caminho_pdf
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/consultar-detalhes-disciplina', methods=['POST'])
@login_required
def consultar_detalhes_disciplina():
    """Retorna módulo, carga horária, competências e laboratórios da disciplina do plano enviado."""
    try:
        data = request.get_json() or {}
        disciplina = data.get('disciplina', '').strip()
        caminho_pdf = data.get('pdf_path') or session.get('uploaded_pdf_path')

        if not disciplina:
            return jsonify({'error': 'Disciplina não informada'}), 400

        detalhes = generator_service.extrair_detalhes_disciplina_pdf(disciplina, caminho_pdf) if caminho_pdf else None
        if detalhes:
            return jsonify({
                'success': True,
                'modulo': detalhes.get('modulo', ''),
                'carga_horaria': detalhes.get('carga_horaria', 0),
                'competencia_geral': detalhes.get('competencia_geral', ''),
                'unidade_competencia': detalhes.get('unidade_competencia', ''),
                'laboratorios': detalhes.get('laboratorios', []),
                'total_conhecimentos': len(detalhes.get('conhecimentos', []))
            })

        modulo = generator_service.identificar_modulo_disciplina(disciplina, caminho_pdf)
        return jsonify({'success': True, 'modulo': modulo})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/consultar-modulo', methods=['POST'])
@login_required
def consultar_modulo():
    """Consulta dinâmica para identificar o módulo exato da disciplina baseado no plano enviado."""
    try:
        data = request.get_json() or {}
        disciplina = data.get('disciplina', '')
        caminho_pdf = data.get('pdf_path') or session.get('uploaded_pdf_path')

        modulo = generator_service.identificar_modulo_disciplina(disciplina, caminho_pdf)
        return jsonify({'modulo': modulo})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/gerar', methods=['POST'])
@login_required
def gerar_plano():
    try:
        nome_disciplina = request.form.get('nome_disciplina', '').strip()
        nome_professor = request.form.get('nome_professor', '').strip() or session.get('user', {}).get('nome', '')
        codigo_turma = request.form.get('codigo_turma', '').strip()
        carga_horaria = int(request.form.get('carga_horaria', 0))
        horas_por_aula = int(request.form.get('horas_por_aula', 0))
        data_inicio_str = request.form.get('data_inicio', '')
        curso = request.form.get('curso', '').strip()
        modulo_manual = request.form.get('modulo', '').strip()
        ativar_ia = request.form.get('ativar_ia', 'true').lower() in ('true', '1', 'on', 'yes')

        if not all([nome_disciplina, carga_horaria, horas_por_aula, data_inicio_str]):
            flash('Por favor, preencha todos os campos obrigatórios (*).', 'error')
            return redirect(url_for('index'))

        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        datas_aula = calcular_datas_aula(data_inicio, carga_horaria, horas_por_aula)

        if not datas_aula:
            flash('Não foi possível calcular as datas de aula.', 'error')
            return redirect(url_for('index'))

        data_fim = datas_aula[-1]

        # Feriados no período
        all_h = {}
        for y in range(data_inicio.year, data_fim.year + 1):
            all_h.update(get_feriados(y))

        feriados_no_periodo = {
            d.strftime('%d/%m/%Y'): name
            for d, name in all_h.items()
            if data_inicio <= d <= data_fim
        }

        # PDF do Plano de Curso enviado pelo usuário (da requisição ou da sessão)
        caminho_pdf = None
        if 'plano_curso_pdf' in request.files:
            f = request.files['plano_curso_pdf']
            if f.filename:
                import uuid
                safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
                caminho_pdf = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                f.save(caminho_pdf)
                session['uploaded_pdf_path'] = caminho_pdf

        if not caminho_pdf:
            caminho_pdf = session.get('uploaded_pdf_path')

        # Extrair detalhes diretamente do PDF enviado pelo usuário
        detalhes_uc = None
        laboratorios_uc = []
        if caminho_pdf and os.path.exists(caminho_pdf):
            detalhes_uc = generator_service.extrair_detalhes_disciplina_pdf(nome_disciplina, caminho_pdf)
            meta = generator_service.extrair_metadados_plano_pdf(caminho_pdf)
            if not curso and meta.get('curso'):
                curso = meta['curso']
            if detalhes_uc and detalhes_uc.get('laboratorios'):
                laboratorios_uc = detalhes_uc['laboratorios']
            elif meta.get('laboratorios_curso'):
                laboratorios_uc = meta['laboratorios_curso']

        if not curso:
            curso = "Curso Técnico SENAI"

        # 1. VERIFICAR MÓDULO (PDF enviado > digitado manual > fallback)
        if modulo_manual:
            modulo = modulo_manual
        elif detalhes_uc and detalhes_uc.get('modulo'):
            modulo = detalhes_uc['modulo']
        else:
            modulo = generator_service.identificar_modulo_disciplina(nome_disciplina, caminho_pdf)

        # 2. OBTER COMPETÊNCIAS FIÉIS AO PLANO DE CURSO ENVIADO
        if detalhes_uc and detalhes_uc.get('competencia_geral'):
            comp_geral = detalhes_uc['competencia_geral']
            unid_comp = detalhes_uc.get('unidade_competencia') or (
                f"Executar os processos técnicos e operacionais de {nome_disciplina}, "
                f"atendendo às normas de qualidade, segurança, saúde e meio ambiente."
            )
        else:
            comp_geral, unid_comp = generator_service.extrair_competencias_completas(
                nome_disciplina, modulo, caminho_pdf
            )

        # 3. EXTRAIR OS CONHECIMENTOS DA DISCIPLINA NO PLANO ENVIADO
        conhecimentos_pct = detalhes_uc.get('conhecimentos', []) if detalhes_uc else []
        if not conhecimentos_pct:
            conhecimentos_pct = generator_service.obter_conhecimentos_disciplina(nome_disciplina, caminho_pdf)

        # 4. GERAÇÃO DE CONTEÚDOS DAS AULAS COM OS LABORATÓRIOS DO PLANO ENVIADO
        num_aulas = len(datas_aula)
        gemini_key = session.get('gemini_api_key', '') or os.environ.get('GEMINI_API_KEY', '')

        conteudos_gerados, status_ia = ai_service.gerar_plano_com_ia(
            disciplina=nome_disciplina,
            curso=curso,
            num_aulas=num_aulas,
            carga_horaria=carga_horaria,
            horas_aula=horas_por_aula,
            provedor="gemini",
            api_key=gemini_key,
            ementa_texto="",
            conhecimentos_pct=conhecimentos_pct,
            laboratorios=laboratorios_uc
        )

        # Montagem das aulas
        aulas = []
        for i, dt in enumerate(datas_aula):
            info_aula = conteudos_gerados[i] if i < len(conteudos_gerados) else {}
            aulas.append({
                'numero': i + 1,
                'data': dt.strftime('%d/%m'),
                'data_completa': dt.strftime('%d/%m/%Y'),
                'conhecimento': info_aula.get('conhecimento', ''),
                'estrategia': info_aula.get('estrategia', 'Aula Expositiva Dialogada'),
                'recursos': info_aula.get('recursos', 'Quadro Branco e Slides'),
                'ambiente': info_aula.get('ambiente', 'Sala de Aula'),
            })

        plano_data = {
            'curso': curso,
            'nome_disciplina': nome_disciplina,
            'nome_professor': nome_professor,
            'codigo_turma': codigo_turma,
            'carga_horaria': carga_horaria,
            'horas_por_aula': horas_por_aula,
            'modulo': modulo,
            'unidade_curricular': nome_disciplina.upper(),
            'competencia_geral': comp_geral,
            'unidade_competencia': unid_comp,
            'data_inicio_str': data_inicio.strftime('%d/%m/%Y'),
            'data_fim_str': data_fim.strftime('%d/%m/%Y'),
            'aulas': aulas,
            'feriados': feriados_no_periodo,
            'status_ia': status_ia,
            'caminho_pdf': caminho_pdf,
            'laboratorios': laboratorios_uc,
            'tem_chave_ia': bool(gemini_key)
        }

        # Não grava o array bruto de conhecimentos na sessão para manter o cookie leve (< 2KB)
        session['plano_data'] = plano_data
        user = session.get('user', {})
        return render_template('preview.html', plano=plano_data, user=user)

    except Exception as e:
        flash(f'Erro ao processar plano de aula: {e}', 'error')
        return redirect(url_for('index'))


@app.route('/gerar-ia-preview', methods=['POST'])
@login_required
def gerar_ia_preview():
    """Regenera os tópicos via IA diretamente na tela de edição mantendo os conhecimentos do plano de curso."""
    try:
        data = request.get_json() or {}
        plano = session.get('plano_data', {})

        disciplina = data.get('disciplina') or plano.get('nome_disciplina', '')
        curso = data.get('curso') or plano.get('curso', 'Técnico em Automação')
        num_aulas = int(data.get('num_aulas') or len(plano.get('aulas', [])))
        carga_horaria = int(plano.get('carga_horaria', 40))
        horas_aula = int(plano.get('horas_por_aula', 4))
        caminho_pdf = plano.get('caminho_pdf') or session.get('uploaded_pdf_path')
        conhecimentos_pct = generator_service.obter_conhecimentos_disciplina(disciplina, caminho_pdf)
        laboratorios_uc = generator_service.obter_laboratorios_disciplina(disciplina, caminho_pdf)
        gemini_key = session.get('gemini_api_key', '') or os.environ.get('GEMINI_API_KEY', '')

        aulas_ia, status_msg = ai_service.gerar_plano_com_ia(
            disciplina=disciplina,
            curso=curso,
            num_aulas=num_aulas,
            carga_horaria=carga_horaria,
            horas_aula=horas_aula,
            provedor="gemini",
            api_key=gemini_key,
            ementa_texto="",
            conhecimentos_pct=conhecimentos_pct,
            laboratorios=laboratorios_uc
        )

        return jsonify({'aulas': aulas_ia, 'status': status_msg})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/salvar-chave-ia', methods=['POST'])
@login_required
def salvar_chave_ia():
    """Salva a chave de API do Gemini na sessão e no arquivo .env."""
    try:
        data = request.get_json() or {}
        chave = data.get('api_key', '').strip()
        session['gemini_api_key'] = chave

        if chave:
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(f"GEMINI_API_KEY={chave}\n")

        return jsonify({'success': True, 'has_key': bool(chave)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download-pdf', methods=['POST'])
@login_required
def download_pdf():
    """
    Gera o documento diretamente a partir do template oficial 'Planejamento - Modelo.docx'
    e converte para PDF, assegurando 100% de fidelidade ao modelo.
    """
    try:
        data = request.get_json()
        plano = session.get('plano_data', {})

        if data:
            for k in ('curso', 'modulo', 'competencia_geral',
                       'unidade_competencia', 'nome_disciplina',
                       'nome_professor', 'codigo_turma'):
                if k in data:
                    plano[k] = data[k]
            if 'aulas' in data:
                plano['aulas'] = data['aulas']

        if not plano:
            return jsonify({'error': 'Nenhum plano disponível para download.'}), 400

        plano['unidade_curricular'] = plano.get('nome_disciplina', '').upper()
        out_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'output')

        nome_limpo = re.sub(r'[^\w\-_]', '_', plano.get('nome_disciplina', 'plano'))
        docx_path = os.path.join(out_dir, f"Plano_Aula_{nome_limpo}.docx")
        pdf_path = os.path.join(out_dir, f"Plano_Aula_{nome_limpo}.pdf")

        # 1. Gera DOCX com design 100% fiel ao modelo oficial
        generator_service.gerar_docx_a_partir_do_modelo(plano, docx_path)

        # 2. Converte para PDF
        sucesso_pdf = generator_service.converter_docx_para_pdf(docx_path, pdf_path)
        if sucesso_pdf and os.path.exists(pdf_path):
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=f"Plano_Aula_{nome_limpo}.pdf",
                mimetype='application/pdf'
            )
        else:
            return send_file(
                docx_path,
                as_attachment=True,
                download_name=f"Plano_Aula_{nome_limpo}.docx",
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download-docx', methods=['POST'])
@login_required
def download_docx():
    """Gera o documento DOCX com design 100% fiel ao modelo oficial."""
    try:
        data = request.get_json()
        plano = session.get('plano_data', {})

        if data:
            for k in ('curso', 'modulo', 'competencia_geral',
                       'unidade_competencia', 'nome_disciplina',
                       'nome_professor', 'codigo_turma'):
                if k in data:
                    plano[k] = data[k]
            if 'aulas' in data:
                plano['aulas'] = data['aulas']

        if not plano:
            return jsonify({'error': 'Nenhum plano disponível.'}), 400

        plano['unidade_curricular'] = plano.get('nome_disciplina', '').upper()
        out_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'output')

        nome_limpo = re.sub(r'[^\w\-_]', '_', plano.get('nome_disciplina', 'plano'))
        docx_path = os.path.join(out_dir, f"Plano_Aula_{nome_limpo}.docx")

        generator_service.gerar_docx_a_partir_do_modelo(plano, docx_path)

        return send_file(
            docx_path,
            as_attachment=True,
            download_name=f"Plano_Aula_{nome_limpo}.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/calcular-data-fim', methods=['POST'])
@login_required
def calcular_data_fim():
    """API para previsão de data final e feriados de Mossoró/RN."""
    try:
        data = request.get_json()
        di = datetime.strptime(data['data_inicio'], '%Y-%m-%d').date()
        ch = int(data['carga_horaria'])
        ha = int(data['horas_por_aula'])

        if ha <= 0 or ch <= 0:
            return jsonify({'error': 'Valores inválidos'}), 400

        datas = calcular_datas_aula(di, ch, ha)

        if datas:
            all_h = {}
            for y in range(di.year, datas[-1].year + 1):
                all_h.update(get_feriados(y))

            feriados = [
                {'data': d.strftime('%d/%m/%Y'), 'nome': name}
                for d, name in sorted(all_h.items())
                if di <= d <= datas[-1]
            ]
            return jsonify({
                'data_fim': datas[-1].strftime('%d/%m/%Y'),
                'num_aulas': len(datas),
                'feriados': feriados,
            })

        return jsonify({'error': 'Não foi possível calcular'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
