import os
import re
import json
import unicodedata
from copy import deepcopy
from docx import Document
import pdfplumber

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Planejamento - Modelo.docx')
BANCO_CONHECIMENTOS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'banco_conhecimentos_pct.json')

# ============================================================
# MAPA OFICIAL DE MÓDULOS DO SENAI (CONFORME PÁGS 22-24 DO PCT)
# ============================================================

MAPA_CANONICO_MODULOS = {
    # Módulo BÁSICO
    'introducao a tecnologia da informacao e comunicacao': 'Básico',
    'tecnologia da informacao e comunicacao': 'Básico',
    'sustentabilidade nos processos industriais': 'Básico',
    'sustentabilidade': 'Básico',
    'introducao a qualidade e produtividade': 'Básico',
    'qualidade e produtividade': 'Básico',
    'introducao a industria 4.0': 'Básico',
    'industria 4.0': 'Básico',
    'saude e seguranca no trabalho': 'Básico',
    'saude, seguranca no trabalho': 'Básico',
    'introducao ao desenvolvimento de projetos': 'Básico',
    'desenvolvimento de projetos': 'Básico',

    # Módulo INTRODUTÓRIO
    'desenho tecnico aplicado a projetos eletricos': 'Introdutório',
    'desenho tecnico': 'Introdutório',
    'fundamentos de eletricidade': 'Introdutório',
    'eletricidade basica': 'Introdutório',
    'fundamentos de sistemas eletricos': 'Introdutório',
    'sistemas eletricos': 'Introdutório',

    # Módulo ESPECÍFICO I
    'instalacao e manutencao eletrica predial': 'Específico I',
    'instalacoes eletricas prediais': 'Específico I',
    'projetos eletricos prediais': 'Específico I',
    'instrumentacao industrial': 'Específico I',

    # Módulo ESPECÍFICO II
    'criatividade e ideacao em projetos de inovacao': 'Específico II',
    'instalacoes e acionamentos eletricos industriais': 'Específico II',
    'acionamentos eletricos': 'Específico II',
    'manutencao eletrica industrial': 'Específico II',
    'fundamentos de eletronica': 'Específico II',
    'eletronica basica': 'Específico II',
    'integracao de sistemas eletricos automatizados': 'Específico II',
    'sistemas automatizados': 'Específico II',
    'projetos eletricos industriais': 'Específico II',
    'elementos finais de controle': 'Específico II',
    'controladores logicos programaveis': 'Específico II',
    'controladores logicos': 'Específico II',
    'clp': 'Específico II',
    'sistemas supervisorios': 'Específico II',
    'redes industriais': 'Específico II',

    # Módulo ESPECÍFICO III
    'prototipagem de negocios inovadores': 'Específico III',
    'modelagem de projetos de inovacao': 'Específico III',
    'integracao de sistemas de energias renovaveis': 'Específico III',
    'energias renovaveis': 'Específico III',
    'instalacoes de sistemas eletricos de potencia - sep': 'Específico III',
    'instalacoes de sistemas eletricos de potencia': 'Específico III',
    'sep': 'Específico III',
    'manutencao e operacao de sistemas eletricos de potencia - sep': 'Específico III',
    'manutencao e operacao de sistemas eletricos de potencia': 'Específico III',
    'projetos de instalacoes eletricas de potencia': 'Específico III',

    # Módulo ESPECÍFICO IV
    'eficiencia energetica': 'Específico IV',
    'implementacao de negocios inovadores': 'Específico IV',
    'gestao operacional integrada': 'Específico IV',
    'tcc': 'Específico IV',
    'estagio supervisionado': 'Específico IV',
    'pratica profissional na empresa': 'Específico IV'
}

def normalizar_texto(texto):
    """Remove acentos e padroniza para minúsculas."""
    if not texto:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFD', str(texto).lower())
        if unicodedata.category(c) != 'Mn'
    ).strip()


def stem_pt(w):
    w = w.lower()
    if w.endswith('is') and len(w) > 4: return w[:-2] + 'l'
    if w.endswith('es') and len(w) > 4: return w[:-2]
    if w.endswith('s') and len(w) > 3: return w[:-1]
    return w

def match_disciplina(d1, d2):
    n1 = normalizar_texto(d1)
    n2 = normalizar_texto(d2)
    if not n1 or not n2 or len(n1) < 3 or len(n2) < 3: return False
    if n1 == n2 or n1 in n2 or n2 in n1: return True
    tokens1 = set(stem_pt(t) for t in n1.split() if len(t) > 2 and t not in ('de', 'da', 'do', 'em', 'para', 'com'))
    tokens2 = set(stem_pt(t) for t in n2.split() if len(t) > 2 and t not in ('de', 'da', 'do', 'em', 'para', 'com'))
    if not tokens1 or not tokens2: return False
    inter = tokens1.intersection(tokens2)
    return len(inter) / min(len(tokens1), len(tokens2)) >= 0.7

def clean_txt(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ''


# ============================================================
# PARSER DINÂMICO DO PLANO DE CURSO (PDF ENVIADO PELO USUÁRIO)
# ============================================================

def extrair_metadados_plano_pdf(pdf_path):
    """
    Analisa qualquer PDF de Plano de Curso do SENAI enviado pelo usuário e extrai:
    - curso: Nome do curso detectado
    - disciplinas: Lista de todas as Unidades Curriculares com módulo e carga horária
    - laboratorios_curso: Todos os laboratórios citados no curso
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return {'curso': '', 'disciplinas': [], 'laboratorios_curso': []}

    curso = ''
    disciplinas = []
    seen_ucs = set()
    laboratorios_curso = set()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_paginas = len(pdf.pages)

            # 1. Detectar nome do curso nas páginas iniciais
            for p in range(min(12, total_paginas)):
                txt = pdf.pages[p].extract_text() or ''
                m = re.search(r'T[ée]cnico\s+em\s+([A-Za-zÀ-Úà-ú\s\-]+?)(?:\s*[-–—]|\s*\n|\s*Eixo|\s*Vers|\s*Área|\s*\(|\s*Resolu|\s*Perfil)', txt, re.IGNORECASE)
                if m:
                    curso = 'Técnico em ' + m.group(1).strip().title()
                    break

            # 2. Percorrer páginas para identificar Unidades Curriculares e Laboratórios
            for idx, page in enumerate(pdf.pages):
                txt = page.extract_text() or ''

                # Buscar laboratórios citados
                labs_found = re.findall(r'Laborat[óo]rio\s*(?:\(s\))?\s*de\s+([A-Za-zÀ-Úà-ú\s\-]+?)(?:[,\.;\n\)]|\s{2,})', txt, re.IGNORECASE)
                for l in labs_found:
                    nome_lab = f"Laboratório de {l.strip().title()}"
                    if 14 < len(nome_lab) < 65 and not any(x in nome_lab.lower() for x in ['ambientes', 'equipamentos', 'etc']):
                        laboratorios_curso.add(nome_lab)

                # Verificar se é página de início de Unidade Curricular
                if 'Unidade Curricular:' in txt:
                    uc_match = re.search(r'Unidade Curricular:\s*([^\n\r]+)', txt, re.IGNORECASE)
                    if uc_match:
                        raw_uc = uc_match.group(1).strip()
                        uc_nome = re.sub(r'\s*Carga\s+Hor[áa]ria:?.*$', '', raw_uc, flags=re.IGNORECASE).strip()
                        uc_nome = re.sub(r'[\.\:\;]$', '', uc_nome).strip()
                        uc_norm = normalizar_texto(uc_nome)

                        if len(uc_nome) >= 4 and uc_norm not in seen_ucs:
                            seen_ucs.add(uc_norm)

                            # Carga Horária
                            ch = 0
                            ch_m = re.search(r'Carga\s+Hor[áa]ria:\s*(\d+)', txt, re.IGNORECASE)
                            if ch_m:
                                ch = int(ch_m.group(1))

                            # Módulo
                            modulo = 'Específico'
                            mod_m = re.search(r'M[óo]dulo:\s*([^\n\r]+?)(?:\s+Perfil|\n|\s+Carga|\s+Unidade|$)', txt, re.IGNORECASE)
                            if mod_m:
                                raw_mod = clean_txt(mod_m.group(1))
                                raw_mod_norm = normalizar_texto(raw_mod)
                                if 'basico' in raw_mod_norm: modulo = 'Básico'
                                elif 'introdutorio' in raw_mod_norm: modulo = 'Introdutório'
                                elif 'especifico i' in raw_mod_norm and 'ii' not in raw_mod_norm and 'iii' not in raw_mod_norm and 'iv' not in raw_mod_norm: modulo = 'Específico I'
                                elif 'especifico ii' in raw_mod_norm: modulo = 'Específico II'
                                elif 'especifico iii' in raw_mod_norm: modulo = 'Específico III'
                                elif 'especifico iv' in raw_mod_norm: modulo = 'Específico IV'
                                else: modulo = raw_mod.title()

                            disciplinas.append({
                                'nome': uc_nome,
                                'modulo': modulo,
                                'carga_horaria': ch,
                                'pagina': idx + 1
                            })
    except Exception as e:
        print(f"Erro ao analisar metadados do PDF: {e}")

    return {
        'curso': curso,
        'disciplinas': disciplinas,
        'laboratorios_curso': sorted(list(laboratorios_curso))
    }


def extrair_detalhes_disciplina_pdf(disciplina, pdf_path):
    """
    Localiza e extrai os detalhes exatos da disciplina a partir do PDF fornecido:
    - modulo
    - carga_horaria
    - competencia_geral (Objetivo Geral)
    - unidade_competencia (Função / Unidade de Competência)
    - conhecimentos (Lista de conhecimentos formativos)
    - laboratorios (Ambientes pedagógicos da UC)
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return None

    detalhes = {
        'modulo': '',
        'carga_horaria': 0,
        'competencia_geral': '',
        'unidade_competencia': '',
        'conhecimentos': [],
        'laboratorios': []
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_paginas = len(pdf.pages)
            pag_inicio = -1

            # Localizar onde a Unidade Curricular começa
            for idx, page in enumerate(pdf.pages):
                txt = page.extract_text() or ''
                if 'Unidade Curricular:' in txt:
                    m = re.search(r'Unidade Curricular:\s*([^\n\r]+)', txt, re.IGNORECASE)
                    if m:
                        raw_uc = m.group(1).strip()
                        uc_nome = re.sub(r'\s*Carga\s+Hor[áa]ria:?.*$', '', raw_uc, flags=re.IGNORECASE).strip()
                        uc_nome = re.sub(r'[\.\:\;]$', '', uc_nome).strip()
                        if match_disciplina(disciplina, uc_nome):
                            pag_inicio = idx
                            break

            if pag_inicio == -1:
                return None

            # Isolar o trecho pertencente estritamente a esta UC
            fatias_texto = []
            paginas_uc = [pag_inicio]

            p0_txt = pdf.pages[pag_inicio].extract_text() or ''
            pos_uc = p0_txt.find('Unidade Curricular:')
            pos_inicio = max(0, pos_uc - 150)
            
            pos_proxima_uc = p0_txt.find('Unidade Curricular:', pos_uc + 20)
            if pos_proxima_uc != -1:
                fatias_texto.append(p0_txt[pos_inicio:pos_proxima_uc])
            else:
                fatias_texto.append(p0_txt[pos_inicio:])
                for off in range(1, 25):
                    p = pag_inicio + off
                    if p >= total_paginas:
                        break
                    p_txt = pdf.pages[p].extract_text() or ''
                    pos_prox = p_txt.find('Unidade Curricular:')
                    if pos_prox != -1:
                        fatias_texto.append(p_txt[:pos_prox])
                        paginas_uc.append(p)
                        break
                    else:
                        fatias_texto.append(p_txt)
                        paginas_uc.append(p)

            bloco_completo = "\n".join(fatias_texto)

            # 1. Módulo
            mod_m = re.search(r'M[óo]dulo:\s*([^\n\r]+?)(?:\s+Perfil|\n|\s+Carga|\s+Unidade|$)', bloco_completo, re.IGNORECASE)
            if mod_m:
                raw_mod = clean_txt(mod_m.group(1))
                raw_mod_norm = normalizar_texto(raw_mod)
                if 'basico' in raw_mod_norm: detalhes['modulo'] = 'Básico'
                elif 'introdutorio' in raw_mod_norm: detalhes['modulo'] = 'Introdutório'
                elif 'especifico i' in raw_mod_norm and 'ii' not in raw_mod_norm and 'iii' not in raw_mod_norm and 'iv' not in raw_mod_norm: detalhes['modulo'] = 'Específico I'
                elif 'especifico ii' in raw_mod_norm: detalhes['modulo'] = 'Específico II'
                elif 'especifico iii' in raw_mod_norm: detalhes['modulo'] = 'Específico III'
                elif 'especifico iv' in raw_mod_norm: detalhes['modulo'] = 'Específico IV'
                else: detalhes['modulo'] = raw_mod.title()

            # 2. Carga Horária
            ch_m = re.search(r'Carga\s+Hor[áa]ria:\s*(\d+)', bloco_completo, re.IGNORECASE)
            if ch_m:
                detalhes['carga_horaria'] = int(ch_m.group(1))

            # 3. Objetivo Geral / Competência Geral
            obj_m = re.search(r'Objetivo Geral:\s*([^\n\r]+(?:\n[^\n\r]+){1,5})', bloco_completo)
            if obj_m:
                raw_obj = obj_m.group(1)
                raw_obj = re.split(r'\n\s*(?:CONTE[ÚU]DO|Conte[úu]do|Elemento|Padr[ãa]o|Subfun[çc]|Fun[çc][ãa]o)', raw_obj, flags=re.IGNORECASE)[0]
                detalhes['competencia_geral'] = clean_txt(raw_obj)

            # 4. Função / Unidade de Competência
            func_m = re.search(r'Fun[çc][ãa]o\s*\n\s*(?:[•\-]?\s*)?(?:F\.\d+:?\s*)?([^\n\r]+(?:\n[^\n\r]+){1,4})', bloco_completo)
            if not func_m:
                func_m = re.search(r'Unidade[s]?\s+de\s+Compet[êe]ncia[:\s]+([^\n\r]+(?:\n[^\n\r]+){1,4})', bloco_completo)
            if func_m:
                raw_func = func_m.group(1)
                raw_func = re.split(r'\n\s*(?:Objetivo|CONTE[ÚU]DO|Conte[úu]do|Elemento|Padr[ãa]o|Subfun[çc])', raw_func, flags=re.IGNORECASE)[0]
                detalhes['unidade_competencia'] = clean_txt(raw_func)

            # 5. Laboratórios da disciplina
            labs = set()
            for l in re.findall(r'Laborat[óo]rio\s*(?:\(s\))?\s*de\s+([A-Za-zÀ-Úà-ú\s\-]+?)(?:[,\.;\n\)]|\s{2,}|$)', bloco_completo, re.IGNORECASE):
                nome_l = f"Laboratório de {l.strip().title()}"
                if 14 < len(nome_l) < 65 and not any(x in nome_l.lower() for x in ['ambientes', 'equipamentos', 'etc']):
                    labs.add(nome_l)

            detalhes['laboratorios'] = sorted(list(labs))

            # 6. Conhecimentos da disciplina
            conhecimentos = []
            termos_bloqueados = (
                'reconhecer', 'identificar', 'demonstrar', 'aplicar', 'analisar',
                'sala de aula', 'quadro branco', 'microcomputador', 'biblioteca',
                'projetor', 'flip chart', 'kit didatico', 'calculadora', 'aderir',
                'motivar', 'aceitar', 'posicionar', 'valorizar', 'acatar',
                'compreender', 'assumir', 'respeitar', 'comprometer', 'adotar',
                'estimular', 'instigar'
            )

            for linha in bloco_completo.split('\n'):
                l = linha.strip()
                if re.match(r'^\d+(\.\d+)*\s+[A-ZÀ-Úa-zà-ú]', l):
                    item = clean_txt(re.sub(r'^\d+(\.\d+)*\s*', '', l))
                    if len(item) > 3 and not any(normalizar_texto(item).startswith(b) for b in termos_bloqueados) and item not in conhecimentos:
                        conhecimentos.append(item)
                elif re.match(r'^[➢\•\-]\s+[A-ZÀ-Úa-zà-ú]', l):
                    item = clean_txt(re.sub(r'^[➢\•\-]\s*', '', l))
                    if len(item) > 3 and not any(normalizar_texto(item).startswith(b) for b in termos_bloqueados) and item not in conhecimentos:
                        conhecimentos.append(item)

            detalhes['conhecimentos'] = conhecimentos

    except Exception as e:
        print(f"Erro ao extrair detalhes da disciplina do PDF: {e}")

    return detalhes


def identificar_modulo_disciplina(disciplina, pdf_path=None):
    """
    Identifica o Módulo da disciplina com prioridade absoluta no PDF do usuário.
    """
    disc_norm = normalizar_texto(disciplina)

    # 1. Prioridade 1: Extrair do PDF do Plano de Curso enviado pelo usuário
    if pdf_path and os.path.exists(pdf_path):
        detalhes = extrair_detalhes_disciplina_pdf(disciplina, pdf_path)
        if detalhes and detalhes.get('modulo'):
            return detalhes['modulo']

    # 2. Fallback: Mapa oficial padrão apenas se não houver PDF
    for chave, mod in MAPA_CANONICO_MODULOS.items():
        chave_norm = normalizar_texto(chave)
        if chave_norm == disc_norm or chave_norm in disc_norm or disc_norm in chave_norm:
            return mod

    # 3. Inferência inteligente genérica
    if any(k in disc_norm for k in ['fundamento', 'desenho', 'basica']):
        return 'Introdutório'
    if any(k in disc_norm for k in ['introducao', 'saude', 'seguranca', 'sustentabilidade', 'qualidade']):
        return 'Básico'
    if any(k in disc_norm for k in ['predial', 'prediais']):
        return 'Específico I'
    if any(k in disc_norm for k in ['potencia', 'sep', 'renovavel']):
        return 'Específico III'
    if any(k in disc_norm for k in ['eficiencia', 'gestao', 'tcc']):
        return 'Específico IV'

    return 'Específico'


def extrair_competencias_completas(disciplina, modulo, pdf_path=None):
    """
    Extrai Competência Geral (Objetivo Geral) e Unidade de Competência (Função)
    diretamente do PDF do Plano de Curso enviado pelo usuário.
    """
    # 1. Prioridade 1: PDF do Plano de Curso enviado pelo usuário
    if pdf_path and os.path.exists(pdf_path):
        detalhes = extrair_detalhes_disciplina_pdf(disciplina, pdf_path)
        if detalhes:
            comp_geral = detalhes.get('competencia_geral')
            unid_comp = detalhes.get('unidade_competencia')
            if comp_geral and unid_comp:
                return comp_geral, unid_comp
            elif comp_geral:
                return comp_geral, (
                    f"Executar as atividades técnicas, operacionais e de projetos relacionadas a {disciplina}, "
                    f"seguindo normas técnicas, de qualidade, saúde e segurança e de meio ambiente."
                )

    # 2. Formulação padrão contextualizada caso o PDF não possua o campo preenchido
    comp_geral = (
        f"Desenvolver as capacidades técnicas, sociais, organizativas e metodológicas "
        f"requeridas para a especificação e aplicação de {disciplina}, levando em "
        f"consideração as diretrizes técnicas e as normas operacionais."
    )
    unid_comp = (
        f"Executar processos de planejamento, operação e controle aplicados a {disciplina}, "
        f"considerando as normas, padrões e requisitos técnicos, de qualidade, "
        f"saúde e segurança e de meio ambiente."
    )
    return comp_geral, unid_comp


def obter_conhecimentos_disciplina(disciplina, pdf_path=None):
    """
    Retorna a lista de 'Conhecimentos' da disciplina. Prioriza o PDF enviado pelo usuário.
    """
    # 1. Prioridade 1: Extração direta do PDF enviado pelo usuário
    if pdf_path and os.path.exists(pdf_path):
        detalhes = extrair_detalhes_disciplina_pdf(disciplina, pdf_path)
        if detalhes and detalhes.get('conhecimentos') and len(detalhes['conhecimentos']) > 0:
            return detalhes['conhecimentos']

    # 2. Fallback: Banco local caso nenhum PDF seja fornecido
    disc_norm = normalizar_texto(disciplina)
    if os.path.exists(BANCO_CONHECIMENTOS_PATH):
        try:
            with open(BANCO_CONHECIMENTOS_PATH, 'r', encoding='utf-8') as f:
                banco = json.load(f)
                for uc_nome, conhs in banco.items():
                    uc_norm = normalizar_texto(uc_nome)
                    if disc_norm in uc_norm or uc_norm in disc_norm:
                        if conhs and len(conhs) > 0:
                            return conhs
        except Exception as e:
            print(f"Erro ao ler banco_conhecimentos_pct.json: {e}")

    # 3. Fallback técnico contextualizado para a disciplina
    return [
        f"Fundamentos, Aplicações e Normas Técnicas em {disciplina}",
        f"Simbologia, Nomenclatura e Interpretação de Diagramas de {disciplina}",
        f"Princípios de Funcionamento e Características Operacionais",
        f"Arquitetura, Interfaces e Especificações de Fabricantes",
        f"Procedimentos de Segurança, Saúde e Normas Regulamentadoras",
        f"Técnicas de Instalação, Parametrização e Configuração",
        f"Práticas de Comandos, Ajustes e Calibração",
        f"Instrumentação, Medições Técnicas e Análise de Desempenho",
        f"Diagnóstico de Anomalias e Resolução de Problemas",
        f"Manutenção Preventiva, Preditiva e Corretiva",
        f"Estudo de Caso e Aplicações Industriais Reais"
    ]


def obter_laboratorios_disciplina(disciplina, pdf_path=None):
    """
    Retorna os laboratórios oficiais para a disciplina a partir do PDF do plano de curso enviado pelo usuário.
    """
    if pdf_path and os.path.exists(pdf_path):
        detalhes = extrair_detalhes_disciplina_pdf(disciplina, pdf_path)
        if detalhes and detalhes.get('laboratorios') and len(detalhes['laboratorios']) > 0:
            return detalhes['laboratorios']

        meta = extrair_metadados_plano_pdf(pdf_path)
        if meta and meta.get('laboratorios_curso'):
            return meta['laboratorios_curso']

    return []


# ============================================================
# GERAÇÃO DO DOCUMENTO 100% IDÊNTICO AO MODELO ENVIADO
# ============================================================

def gerar_docx_a_partir_do_modelo(dados, output_docx):
    """
    Abre diretamente o arquivo 'Planejamento - Modelo.docx', preenchendo
    as tabelas e mantendo 100% dos cabeçalhos, logos, margens, bordas e assinaturas.
    """
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Arquivo de modelo não encontrado: {TEMPLATE_PATH}")

    doc = Document(TEMPLATE_PATH)

    # ---------------- TABELA 0: INFORMAÇÕES DO CURSO ----------------
    t0 = doc.tables[0]

    def set_cell_bold_label(cell, label, valor):
        cell.text = ''
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = 0
        p.paragraph_format.space_after = 0
        r_lbl = p.add_run(label + ' ')
        r_lbl.bold = True
        r_lbl.font.name = 'Calibri'
        r_val = p.add_run(str(valor))
        r_val.bold = False
        r_val.font.name = 'Calibri'

    # Linha 0
    set_cell_bold_label(t0.cell(0, 0), 'Curso:', dados.get('curso', 'Técnico em Automação'))
    set_cell_bold_label(t0.cell(0, 1), 'Carga-horária:', f"{dados.get('carga_horaria', '')}h")
    set_cell_bold_label(t0.cell(0, 2), 'Data:', f"{dados.get('data_inicio_str', '')} até {dados.get('data_fim_str', '')}")

    # Linha 1
    set_cell_bold_label(t0.cell(1, 0), 'Módulo:', dados.get('modulo', 'Específico II'))
    set_cell_bold_label(t0.cell(1, 2), 'Unidade Curricular:', dados.get('unidade_curricular', ''))

    # Linha 2 (mesclada com todas as colunas)
    set_cell_bold_label(t0.cell(2, 0), 'Competência Geral:', dados.get('competencia_geral', ''))

    # Linha 3 (mesclada com todas as colunas)
    set_cell_bold_label(t0.cell(3, 0), 'Unidade(s) de Competência:', dados.get('unidade_competencia', ''))

    # ---------------- TABELA 1: CRONOGRAMA DE AULAS ----------------
    t1 = doc.tables[1]
    template_tr = deepcopy(t1.rows[1]._tr)

    # Remove as linhas em branco pré-existentes do modelo
    while len(t1.rows) > 1:
        t1._tbl.remove(t1.rows[1]._tr)

    aulas = dados.get('aulas', [])
    carga_total = dados.get('carga_horaria', '')

    for idx, aula in enumerate(aulas):
        new_tr = deepcopy(template_tr)
        t1._tbl.append(new_tr)
        row = t1.rows[idx + 1]

        # Coluna 0: Aulas (mostra a carga horária total apenas na primeira linha, igual ao modelo)
        c0 = row.cells[0]
        c0.text = str(carga_total) if idx == 0 else ''
        if c0.paragraphs:
            for r in c0.paragraphs[0].runs: r.font.name = 'Calibri'

        # Coluna 1: Data
        c1 = row.cells[1]
        c1.text = aula.get('data', '')
        if c1.paragraphs:
            for r in c1.paragraphs[0].runs: r.font.name = 'Calibri'

        # Coluna 2: Conhecimento (s)
        c2 = row.cells[2]
        c2.text = aula.get('conhecimento', '')
        if c2.paragraphs:
            for r in c2.paragraphs[0].runs: r.font.name = 'Calibri'

        # Coluna 3: Estratégia de Ensino
        c3 = row.cells[3]
        c3.text = aula.get('estrategia', 'Aula Expositiva')
        if c3.paragraphs:
            for r in c3.paragraphs[0].runs: r.font.name = 'Calibri'

        # Coluna 4: Recursos Didáticos
        c4 = row.cells[4]
        c4.text = aula.get('recursos', 'Quadro Branco e Slides')
        if c4.paragraphs:
            for r in c4.paragraphs[0].runs: r.font.name = 'Calibri'

        # Coluna 5: Ambiente Pedagógico
        c5 = row.cells[5]
        c5.text = aula.get('ambiente', 'Sala de Aula')
        if c5.paragraphs:
            for r in c5.paragraphs[0].runs: r.font.name = 'Calibri'

    doc.save(output_docx)
    return output_docx


def converter_docx_para_pdf(docx_path, pdf_path):
    """Converte o documento para PDF mantendo layout 100% idêntico."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass

    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return True
    except Exception as e:
        print(f"Erro na conversão docx2pdf: {e}")

    return False
