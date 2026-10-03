import os
import json
import re
import urllib.request
import urllib.error

# ==============================================================================
# NOMES OFICIAIS DE LABORATÓRIOS DO PLANO DE CURSO DO SENAI (PCT)
# ==============================================================================
LAB_INFORMATICA = "Laboratório de Informática"
LAB_INDUSTRIAIS = "Laboratório de Instalações Elétricas Industriais"  # "Laboratório de Industriais"
LAB_PREDIAIS = "Laboratório de Instalações Elétricas Prediais"        # "Laboratório de Prediais"
LAB_ACIONAMENTOS = "Laboratório de Acionamentos e Comandos Elétricos"
LAB_AUTOMACAO = "Laboratório de Automação Industrial"
LAB_INSTRUMENTACAO = "Laboratório de Instrumentação"
LAB_ELETRICIDADE = "Laboratório de Eletricidade"
LAB_DESENHO = "Laboratório de Desenho"
LAB_SEP = "Laboratório de Redes de Distribuição de Média e Baixa Tensão"
LAB_EFICIENCIA = "Laboratório de Eficiência Energética"
LAB_FOTOVOLTAICA = "Laboratório de Energia Fotovoltaica"

# Mapeamento de laboratórios oficiais por Unidade Curricular do SENAI
MAPA_LABORATORIOS_PCT = {
    'projetos eletricos industriais': [LAB_INFORMATICA, LAB_INDUSTRIAIS],
    'instalacoes e acionamentos eletricos industriais': [LAB_INDUSTRIAIS, LAB_ACIONAMENTOS, LAB_INFORMATICA],
    'elementos finais de controle': [LAB_INSTRUMENTACAO, LAB_AUTOMACAO, LAB_INFORMATICA],
    'integracao de sistemas eletricos automatizados': [LAB_AUTOMACAO, LAB_INFORMATICA],
    'projetos eletricos prediais': [LAB_INFORMATICA, LAB_PREDIAIS, LAB_DESENHO],
    'instalacao e manutencao eletrica predial': [LAB_PREDIAIS, LAB_INFORMATICA, LAB_DESENHO],
    'fundamentos de eletricidade': [LAB_ELETRICIDADE, LAB_INFORMATICA],
    'fundamentos de sistemas eletricos': [LAB_ELETRICIDADE, LAB_INFORMATICA],
    'desenho tecnico aplicado a projetos eletricos': [LAB_DESENHO, LAB_INFORMATICA],
    'manutencao eletrica industrial': [LAB_INDUSTRIAIS, LAB_INFORMATICA],
    'instalacoes de sistemas eletricos de potencia - sep': [LAB_SEP, LAB_INFORMATICA],
    'manutencao e operacao de sistemas eletricos de': [LAB_SEP, LAB_INFORMATICA],
    'projetos de instalacoes eletricas de potencia': [LAB_INFORMATICA, LAB_SEP],
    'eficiencia energetica': [LAB_EFICIENCIA, LAB_INFORMATICA],
    'integracao de sistemas de energias renovaveis': [LAB_FOTOVOLTAICA, LAB_INFORMATICA],
    'introducao ao desenvolvimento de projetos': [LAB_INFORMATICA, LAB_DESENHO],
    'introducao a tecnologia da informacao e comunicacao': [LAB_INFORMATICA],
    'introducao a industria 4.0': [LAB_INFORMATICA, LAB_AUTOMACAO]
}

def obter_laboratorios_disciplina(disciplina):
    """Retorna os laboratórios oficiais presentes no Plano de Curso para a disciplina."""
    disc_norm = normalizar_texto(disciplina)
    for chave, labs in MAPA_LABORATORIOS_PCT.items():
        if chave in disc_norm or disc_norm in chave:
            return labs
    
    # Inferência inteligente por palavras-chave
    if any(k in disc_norm for k in ['industrial', 'industriais']):
        return [LAB_INDUSTRIAIS, LAB_INFORMATICA]
    if any(k in disc_norm for k in ['predial', 'prediais', 'residencia']):
        return [LAB_PREDIAIS, LAB_INFORMATICA]
    if any(k in disc_norm for k in ['automacao', 'clp', 'controlador']):
        return [LAB_AUTOMACAO, LAB_INFORMATICA]
    if any(k in disc_norm for k in ['instrumentacao', 'valvula', 'controle']):
        return [LAB_INSTRUMENTACAO, LAB_AUTOMACAO]
    if any(k in disc_norm for k in ['eletricidade', 'circuito']):
        return [LAB_ELETRICIDADE, LAB_INFORMATICA]
    if any(k in disc_norm for k in ['desenho', 'cad', 'projeto']):
        return [LAB_INFORMATICA, LAB_DESENHO]
    if any(k in disc_norm for k in ['potencia', 'sep', 'rede']):
        return [LAB_SEP, LAB_INFORMATICA]
    if any(k in disc_norm for k in ['solar', 'renovavel', 'fotovoltaica']):
        return [LAB_FOTOVOLTAICA, LAB_INFORMATICA]
    
    return [LAB_INFORMATICA, LAB_ELETRICIDADE]


# Carrega chave .env se existir
def carregar_chave_env():
    """Tenta ler GEMINI_API_KEY do ambiente ou do arquivo .env."""
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if key:
        return key
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('GEMINI_API_KEY='):
                        return line.strip().split('=', 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return ''


def chamar_gemini(api_key, prompt):
    """Chama a API do Google Gemini com fallback automático de modelos."""
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("Chave de API do Gemini não fornecida.")

    modelos = [
        "gemini-1.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro"
    ]

    ultimo_erro = None
    for modelo in modelos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 3072,
            }
        }
        headers = {"Content-Type": "application/json"}
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                result = json.loads(response.read().decode('utf-8'))
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return text
        except Exception as e:
            ultimo_erro = e
            continue

    raise RuntimeError(f"Erro ao chamar Google Gemini: {ultimo_erro}")


def parsear_resposta_json(texto_ia, num_aulas):
    """Limpa e converte a resposta da IA em lista de dicionários."""
    limpo = re.sub(r'```json\s*', '', texto_ia, flags=re.IGNORECASE)
    limpo = re.sub(r'```\s*', '', limpo).strip()

    match = re.search(r'\[\s*\{.*\}\s*\]', limpo, re.DOTALL)
    if match:
        dados = json.loads(match.group(0))
        if isinstance(dados, list) and len(dados) > 0:
            return dados

    match_lista = re.search(r'\[\s*".*"\s*\]', limpo, re.DOTALL)
    if match_lista:
        dados = json.loads(match_lista.group(0))
        if isinstance(dados, list):
            return [{"conhecimento": str(x)} for x in dados]

    raise ValueError("Formato JSON não encontrado na resposta da IA")


def normalizar_texto(texto):
    if not texto:
        return ""
    import unicodedata
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').lower().strip()


# ==============================================================================
# MOTOR DE CONTEXTUALIZAÇÃO PEDAGÓGICA SENAI (BUILT-IN AI GENERATOR)
# ==============================================================================

def gerar_conteudos_contextualizados(disciplina, num_aulas, carga_horaria=0, horas_aula=4, conhecimentos_pct=None, laboratorios=None):
    """
    Gera a sequência pedagógica contextualizada oficial do SENAI baseando-se estritamente
    no Plano de Curso enviado pelo usuário:
    - Contextualização rica e resumida (máximo 1 a 2 linhas por aula);
    - Em disciplinas de projetos: aulas teóricas iniciais e etapas práticas de projeto;
    - Em disciplinas laboratoriais: mescla teoria e práticas com laboratórios oficiais do curso enviado;
    - No ambiente pedagógico: utiliza os laboratórios do Plano de Curso enviado ou Sala de Aula para teóricas;
    - Aula 1: Apresentação da Disciplina;
    - Penúltima aula: Avaliação Final;
    - Última aula: Recuperação.
    """
    disc_norm = normalizar_texto(disciplina)

    if num_aulas <= 0:
        return []

    if num_aulas == 1:
        return [{
            "conhecimento": "Apresentação da disciplina e visão geral do conteúdo programático.",
            "estrategia": "Aula Expositiva Dialogada",
            "recursos": "Quadro Branco e Slides",
            "ambiente": "Sala de Aula"
        }]

    # Se foram fornecidos conhecimentos do Plano de Curso enviado pelo usuário, prioriza a montagem dinâmica fiel ao plano
    if conhecimentos_pct and len(conhecimentos_pct) >= 4:
        return _gerar_plano_dinamico_pct(disciplina, num_aulas, conhecimentos_pct, laboratorios=laboratorios)

    # 1. DISCIPLINAS DE PROJETOS
    if any(k in disc_norm for k in ['projeto eletrico industrial', 'projetos eletricos industriais', 'projetos industriais']):
        return _gerar_plano_projetos_industriais(num_aulas)

    if any(k in disc_norm for k in ['projeto eletrico predial', 'projetos eletricos prediais', 'projetos prediais']):
        return _gerar_plano_projetos_prediais(num_aulas)

    if any(k in disc_norm for k in ['projeto', 'desenho tecnico aplicado a projetos']):
        return _gerar_plano_projetos_generico(disciplina, num_aulas)

    # 2. DISCIPLINAS OPERACIONAIS E LABORATORIAIS ESPECÍFICAS
    if 'elementos finais de controle' in disc_norm:
        return _gerar_plano_elementos_finais(num_aulas)

    if any(k in disc_norm for k in ['instalacoes e acionamentos', 'acionamentos eletricos', 'comandos eletricos']):
        return _gerar_plano_acionamentos_industriais(num_aulas)

    if any(k in disc_norm for k in ['clp', 'controlador logico', 'automatizados', 'automacao']):
        return _gerar_plano_clp_automacao(num_aulas)

    if any(k in disc_norm for k in ['fundamentos de eletricidade', 'eletricidade basica']):
        return _gerar_plano_fundamentos_eletricidade(num_aulas)

    if any(k in disc_norm for k in ['manutencao eletrica industrial', 'manutencao industrial']):
        return _gerar_plano_manutencao_industrial(num_aulas)

    if any(k in disc_norm for k in ['sistemas eletricos de potencia', 'sep']):
        return _gerar_plano_sep(num_aulas)

    if 'eficiencia energetica' in disc_norm:
        return _gerar_plano_eficiencia_energetica(num_aulas)

    # 3. GERADOR DINÂMICO PARA QUALQUER DISCIPLINA DO PLANO DE CURSO ENVIADO
    return _gerar_plano_dinamico_pct(disciplina, num_aulas, conhecimentos_pct, laboratorios=laboratorios)



# ==============================================================================
# SUB-GERADORES ESPECIALIZADOS
# ==============================================================================

def _gerar_plano_projetos_industriais(num_aulas):
    """
    Gera o plano para Projetos Elétricos Industriais:
    - ~10 primeiras aulas teóricas (conceitos, normas NBR 5410/5419, cálculos de demanda, condutores, proteção e acionamentos)
    - Demais aulas: etapas de elaboração de um projeto elétrico industrial em CAD e laboratório de industriais
    - Ambientes do PCT: Sala de Aula, Laboratório de Informática e Laboratório de Instalações Elétricas Industriais
    """
    teoricas = [
        ("Apresentação da disciplina, requisitos do projeto elétrico industrial e normas regulamentadoras aplicadas.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Leitura e interpretação de projetos arquitetônicos industriais e levantamento de necessidades e cargas fabris.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Normas técnicas aplicadas a instalações industriais: NBR 5410, NBR 5419 e padrões da concessionária de energia.",
         "Estudo de Normas Técnicas", "Quadro Branco e Apostila", "Sala de Aula"),
        ("Metodologia de cálculo luminotécnico industrial: método dos lúmens, cavidades zonais e eficiência energética.",
         "Aula Expositiva e Resolução de Problemas", "Quadro Branco e Calculadora", "Sala de Aula"),
        ("Critérios de dimensionamento de condutores elétricos: capacidade de condução de corrente (Iz) e limite de queda de tensão.",
         "Aula Expositiva e Cálculos Técnicos", "Quadro Branco e Tabelas Técnicas", "Sala de Aula"),
        ("Dimensionamento de infraestrutura e condutos industriais: eletrocalhas, perfilados, leitos de cabos e eletrodutos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Dimensionamento de acionamentos e motores industriais: métodos de partida (direta, estrela-triângulo, soft-starter e inversor).",
         "Aula Expositiva e Estudo de Casos", "Quadro Branco e Catálogos Técnicos", "Sala de Aula"),
        ("Dimensionamento e seletividade de dispositivos de proteção contra sobrecargas, correntes de curto-circuito e surtos (DPS).",
         "Aula Expositiva e Análise de Gráficos", "Quadro Branco e Curvas Características", "Sala de Aula"),
        ("Correção do fator de potência em plantas industriais: dimensionamento e especificação de banco de capacitores.",
         "Aula Expositiva e Resolução de Exercícios", "Quadro Branco e Slides", "Sala de Aula"),
        ("Sistemas de Proteção contra Descargas Atmosféricas (SPDA): dimensionamento de captores, descidas e malha de aterramento.",
         "Aula Expositiva Dialogada", "Quadro Branco e Normas Técnicas", "Sala de Aula")
    ]

    praticas_projeto = [
        ("Elaboração de Projeto (Etapa 1): Definição do escopo, análise do leiaute fabril e setorização de cargas em CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 2): Lançamento em planta CAD dos pontos de força motriz, tomadas industriais e iluminação.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 3): Levantamento prático de painéis, centros de controle de motores (CCM) e medição de demandas na planta.",
         "Levantamento Técnico em Campo", "Painéis Industriais e Instrumentos de Medição", LAB_INDUSTRIAIS),
        ("Elaboração de Projeto (Etapa 4): Traçado dos circuitos terminais, caminhamento de eletrocalhas e leitos de cabos em planta CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 5): Dimensionamento em planilha técnica dos condutores dos alimentadores gerais e motores.",
         "Desenvolvimento de Projeto Orientado", "Microcomputadores e Planilhas Técnicas", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 6): Especificação técnica e montagem didática dos dispositivos de manobra e CCMs em bancada.",
         "Desenvolvimento Prático Orientado", "Bancada Didática de Painéis e Catálogos", LAB_INDUSTRIAIS),
        ("Elaboração de Projeto (Etapa 7): Elaboração dos diagramas unifilares e multifilares dos centros de comando de motores em CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 8): Modelagem em CAD do subsistema de captação de SPDA e detalhamento da malha de aterramento.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 9): Consolidação do quadro geral de cargas, cálculo de demanda instalada e equilíbrio de fases.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 10): Elaboração do memorial descritivo, especificações técnicas e lista quantitativa de materiais.",
         "Documentação Técnica de Projeto", "Microcomputadores e Processador de Texto", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 11): Compatibilização de interferências entre projetos, revisão das pranchas e fechamento do projeto.",
         "Revisão Técnica de Projeto", "Microcomputadores e Software CAD", LAB_INFORMATICA)
    ]

    return _combinar_aulas(num_aulas, teoricas, praticas_projeto,
                           nome_avaliacao="Avaliação Final: Entrega e apresentação técnica do projeto elétrico industrial desenvolvido.",
                           amb_avaliacao=LAB_INFORMATICA)


def _gerar_plano_projetos_prediais(num_aulas):
    """Gera o plano para Projetos Elétricos Prediais (NBR 5410)."""
    teoricas = [
        ("Apresentação da disciplina, diretrizes de projetos elétricos prediais e requisitos da norma NBR 5410.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Leitura e interpretação de projetos arquitetônicos residenciais e comerciais e previsão de cargas mínimas.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Divisão da instalação em circuitos terminais: critérios de iluminação, TUGs e TUEs conforme NBR 5410.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Metodologia de cálculo luminotécnico para ambientes residenciais e comerciais e eficiência energética.",
         "Aula Expositiva e Exercícios", "Quadro Branco e Calculadora", "Sala de Aula"),
        ("Dimensionamento de condutores em baixa tensão: capacidade de corrente, agrupamento e queda de tensão admissível.",
         "Aula Expositiva e Cálculos Técnicos", "Quadro Branco e Tabelas Técnicas", "Sala de Aula"),
        ("Dimensionamento de eletrodutos e caixas de passagem: cálculo da taxa máxima de ocupação percentual.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Dispositivos de proteção para instalações prediais: disjuntores termomagnéticos, DR e DPS.",
         "Aula Expositiva Dialogada", "Quadro Branco e Mostruário Didático", "Sala de Aula"),
        ("Dimensionamento do padrão de entrada de energia e quadro de distribuição conforme norma da concessionária.",
         "Aula Expositiva e Análise de Normas", "Quadro Branco e Norma da Concessionária", "Sala de Aula"),
        ("Sistemas de aterramento predial e equipotencialização: eletrodos, condutores de proteção e barramento BEP.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula")
    ]

    praticas_projeto = [
        ("Elaboração de Projeto (Etapa 1): Análise da planta baixa residencial e locação dos pontos de iluminação e tomadas em CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 2): Lançamento dos pontos de comando (interruptores simples, paralelos e intermediários) em CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 3): Traçado da tubulação de eletrodutos e distribuição dos circuitos na planta baixa em CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 4): Indicação e representação da fiação (fase, neutro, retorno e proteção) nos trechos em CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 5): Dimensionamento dos condutores e eletrodutos em planilha e diagramação em prancha técnica.",
         "Desenvolvimento de Projeto Orientado", "Microcomputadores e Planilhas Técnicas", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 6): Elaboração do diagrama unifilar do quadro de distribuição geral (QDG) e proteção DR/DPS.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 7): Montagem do quadro de cargas geral, cálculo de demanda e balanceamento entre fases.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 8): Elaboração do memorial descritivo da instalação predial e lista quantitativa de materiais.",
         "Documentação Técnica de Projeto", "Microcomputadores e Processador de Texto", LAB_INFORMATICA),
        ("Elaboração de Projeto (Etapa 9): Revisão final das pranchas técnicas, notas gerais de projeto e plotagem para aprovação.",
         "Revisão Técnica de Projeto", "Microcomputadores e Software CAD", LAB_INFORMATICA)
    ]

    return _combinar_aulas(num_aulas, teoricas, praticas_projeto,
                           nome_avaliacao="Avaliação Final: Entrega e defesa técnica do projeto elétrico predial desenvolvido.",
                           amb_avaliacao=LAB_INFORMATICA)


def _gerar_plano_elementos_finais(num_aulas):
    """Gera o plano para Elementos Finais de Controle com laboratórios oficiais do PCT."""
    aulas_conteudo = [
        ("Apresentação da disciplina, cronograma pedagógico e introdução aos atuadores em malhas de controle de processos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Tipos construtivos de válvulas de controle: globo, gaveta, borboleta e esfera aplicadas em processos industriais contínuos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Anatomia e partes das válvulas: corpo, castelo, internos (trim) e atuadores pneumáticos e eletromecânicos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Atuadores industriais e posicionadores: princípios de modulação de sinal 4-20mA, ar comprimido e posicionadores inteligentes.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Simbologia técnica de instrumentação e controle conforme norma ISA 5.1 aplicada a malhas de vazão e pressão.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Bancada: Identificação física, desmontagem didática de válvulas industriais e inspeção de sede e obturador.",
         "Aula Prática em Bancada", "Bancada Didática e Ferramentas", LAB_INSTRUMENTACAO),
        ("Dinâmica de vazão e características inerentes de fluxo: linear, igual porcentagem e abertura rápida em processos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Materiais e compatibilidade química: especificação de corpos e gaxetas para fluidos corrosivos, vapor e alta temperatura.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Critérios de seleção e dimensionamento de válvulas de controle: cálculo do coeficiente de vazão (Cv) e queda de pressão.",
         "Aula Expositiva e Cálculos Técnicos", "Quadro Branco e Tabelas Técnicas", "Sala de Aula"),
        ("Fenômenos hidrodinâmicos em válvulas: diagnóstico e prevenção contra cavitação e flashing em sistemas hidráulicos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Classes de vedação conforme norma ANSI/FCI 70-2 e procedimentos de teste de estanqueidade em oficinas de calibração.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Laboratório: Calibração de posicionador eletropneumático inteligente com gerador de corrente 4-20mA.",
         "Aula Prática em Laboratório", "Gerador de Corrente e Posicionador", LAB_INSTRUMENTACAO),
        ("Aula Prática em Bancada: Ensaio de sintonia de malha de controle de nível e resposta temporal do elemento final.",
         "Aula Prática em Bancada", "Bancada Didática de Processos", LAB_AUTOMACAO),
        ("Procedimentos de manutenção preventiva, preditiva e detecção de anomalias em elementos finais de controle.",
         "Estudo de Caso e Manutenção", "Quadro Branco e Manuais Técnicos", "Sala de Aula")
    ]

    return _ajustar_sequencia_direta(num_aulas, aulas_conteudo,
                                     nome_avaliacao="Avaliação Final: Avaliação teórica e prática sobre especificação e calibração de válvulas.",
                                     amb_avaliacao=LAB_INSTRUMENTACAO)


def _gerar_plano_acionamentos_industriais(num_aulas):
    """Gera o plano para Instalações e Acionamentos Elétricos Industriais."""
    aulas_conteudo = [
        ("Apresentação da disciplina, normas de segurança NR-10 e visão geral de acionamentos e motores industriais.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Componentes de comandos elétricos: contatores de potência e auxiliares, botoeiras, sinalizadores e relés térmicos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Componentes Didáticos", "Sala de Aula"),
        ("Motores elétricos trifásicos de indução (MIT): princípios de funcionamento, fechamentos (estrela/triângulo) e placa de identificação.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Bancada: Montagem e ensaio de circuito de comando e força para partida direta de motor trifásico.",
         "Aula Prática em Bancada", "Bancada Didática e Multímetro", LAB_INDUSTRIAIS),
        ("Aula Prática em Bancada: Montagem de circuito de partida direta com reversão de sentido de giro e intertravamento.",
         "Aula Prática em Bancada", "Bancada Didática e Motores", LAB_INDUSTRIAIS),
        ("Partida indireta: dimensionamento e funcionamento de chave de partida estrela-triângulo automática.",
         "Aula Expositiva e Cálculos Técnicos", "Quadro Branco e Esquemas Elétricos", "Sala de Aula"),
        ("Aula Prática em Bancada: Montagem e parametrização do circuito temporizado de partida estrela-triângulo.",
         "Aula Prática em Bancada", "Bancada Didática e Temporizadores", LAB_ACIONAMENTOS),
        ("Dispositivos de proteção industrial: disjuntores motores, fusíveis ultrarrápidos e coordenação tipo 1 e tipo 2.",
         "Aula Expositiva Dialogada", "Quadro Branco e Catálogos Técnicos", "Sala de Aula"),
        ("Acionamentos eletrônicos: princípios de funcionamento e parametrização de chaves de partida suave (soft-starters).",
         "Aula Expositiva Dialogada", "Quadro Branco e Manuais de Fabricante", "Sala de Aula"),
        ("Aula Prática em Laboratório: Parametrização de soft-starter (rampas de aceleração/desaceleração e limites de corrente).",
         "Aula Prática em Laboratório", "Bancada Didática com Soft-Starter", LAB_INDUSTRIAIS),
        ("Inversores de frequência: princípio de variação de velocidade escalar (V/f) e vetorial em motores trifásicos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Laboratório: Parametrização básica de inversor de frequência via IHM e entradas digitais/analógicas.",
         "Aula Prática em Laboratório", "Bancada com Inversor de Frequência", LAB_INDUSTRIAIS),
        ("Aula Prática em Laboratório: Controle de velocidade de motor por potenciômetro externo e frenagem dinâmica.",
         "Aula Prática em Laboratório", "Bancada Didática e Tacômetro", LAB_ACIONAMENTOS),
        ("Diagnóstico de falhas e manutenção em painéis de comando e centros de controle de motores (CCM).",
         "Estudo de Caso e Diagnóstico", "Quadro Branco e Esquemas Elétricos", "Sala de Aula")
    ]

    return _ajustar_sequencia_direta(num_aulas, aulas_conteudo,
                                     nome_avaliacao="Avaliação Final: Montagem prática em bancada e avaliação teórica de acionamentos elétricos.",
                                     amb_avaliacao=LAB_INDUSTRIAIS)


def _gerar_plano_clp_automacao(num_aulas):
    """Gera o plano para Integração de Sistemas Elétricos Automatizados / CLP."""
    aulas_conteudo = [
        ("Apresentação da disciplina, histórico da automação industrial e arquitetura interna de Controladores Lógicos Programáveis (CLP).",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Módulos de E/S digitais e analógicas, ciclo de varredura (scan time) e mapeamento de memória do CLP.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Norma IEC 61131-3 e introdução à programação em Linguagem Ladder: contatos NA, NF, bobinas e relés internos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Software: Criação de projetos e programação básica de lógica booleana em ambiente de simulação.",
         "Prática em Software de Simulação", "Microcomputadores e Software CLP", LAB_INFORMATICA),
        ("Instruções temporizadas (TON, TOF, TP): funcionamento, aplicação industrial e elaboração de lógicas temporizadas.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Software: Programação e simulação de partidas de motores e sequenciamentos industriais temporizados.",
         "Prática em Software de Simulação", "Microcomputadores e Software CLP", LAB_INFORMATICA),
        ("Instruções de contagem (CTU, CTD, CTUD) e detecção de borda de subida/descida em processos fabris.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Bancada: Conexão física de botoeiras, sensores indutivos/ópticos e atuadores às entradas/saídas do CLP.",
         "Aula Prática em Bancada", "Bancada de CLP e Sensores Industriais", LAB_AUTOMACAO),
        ("Aula Prática em Bancada: Transferência de programa para a CPU do CLP e teste de comissionamento em bancada didática.",
         "Aula Prática em Bancada", "Bancada com CLP e Microcomputador", LAB_AUTOMACAO),
        ("Tratamento de sinais analógicos: resolução em bits, conversão A/D e blocos de escalonamento para sensores 4-20mA e 0-10V.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Laboratório: Leitura analógica de transmissores de nível e temperatura e acionamento proporcional.",
         "Aula Prática em Laboratório", "Bancada Didática com Transmissores", LAB_AUTOMACAO),
        ("Introdução a Interfaces Homem-Máquina (IHM): criação de telas de supervisão, botões virtuais e sinalizações gráficas.",
         "Desenvolvimento de Telas de IHM", "Microcomputadores e Software IHM", LAB_INFORMATICA),
        ("Redes de comunicação industrial (Modbus, Profinet/Ethernet Industrial) e integração entre CLP e periféricos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Diagnóstico de falhas de comunicação e rotinas de manutenção em sistemas elétricos automatizados.",
         "Diagnóstico e Resolução de Falhas", "Microcomputadores e CLP", LAB_AUTOMACAO)
    ]

    return _ajustar_sequencia_direta(num_aulas, aulas_conteudo,
                                     nome_avaliacao="Avaliação Final: Desenvolvimento e validação prática de aplicação em bancada com CLP e IHM.",
                                     amb_avaliacao=LAB_AUTOMACAO)


def _gerar_plano_fundamentos_eletricidade(num_aulas):
    """Gera o plano para Fundamentos de Eletricidade."""
    aulas_conteudo = [
        ("Apresentação da disciplina, estrutura da matéria, grandezas elétricas fundamentais (tensão, corrente, resistência e potência).",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Primeira e Segunda Leis de Ohm, resistividade dos materiais condutores e influência da temperatura.",
         "Aula Expositiva e Exercícios", "Quadro Branco e Calculadora", "Sala de Aula"),
        ("Aula Prática em Bancada: Uso correto de instrumentos de medição (multímetro: voltímetro, amperímetro e ohmímetro).",
         "Aula Prática em Bancada", "Bancada Didática e Multímetros", LAB_ELETRICIDADE),
        ("Circuitos resistivos em série e paralelo: propriedades, cálculo de resistência equivalente e divisão de tensão e corrente.",
         "Aula Expositiva e Resolução de Problemas", "Quadro Branco e Calculadora", "Sala de Aula"),
        ("Aula Prática em Bancada: Montagem de circuitos série e paralelo e medição experimental de grandezas elétricas.",
         "Aula Prática em Bancada", "Bancadas Didáticas e Resistores", LAB_ELETRICIDADE),
        ("Leis de Kirchhoff (Lei dos Nós e Lei das Malhas) aplicadas à análise de circuitos mistos de corrente contínua.",
         "Aula Expositiva e Exercícios", "Quadro Branco e Exercícios Práticos", "Sala de Aula"),
        ("Potência elétrica e Energia: efeito Joule, rendimento e cálculo de consumo de energia em quilowatt-hora (kWh).",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Eletromagnetismo: campos magnéticos, indução eletromagnética, Lei de Faraday-Lenz e princípio dos transformadores.",
         "Aula Expositiva Dialogada", "Quadro Branco e Demonstrações Didáticas", "Sala de Aula"),
        ("Corrente Alternada (CA): geração senoidal, frequência, período, valor de pico, valor eficaz (RMS) e defasagem angular.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Laboratório: Medição de sinais alternados senoidais com osciloscópio e gerador de funções.",
         "Aula Prática em Laboratório", "Osciloscópio e Gerador de Funções", LAB_ELETRICIDADE),
        ("Componentes reativos em corrente alternada: comportamento de capacitores, indutores e cálculo de reatâncias.",
         "Aula Expositiva e Exercícios", "Quadro Branco e Calculadora", "Sala de Aula"),
        ("Potências em corrente alternada: potência ativa (W), reativa (VAr), aparente (VA) e triângulo de potências.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Sistemas trifásicos equilibrados: tensões de fase e de linha, conexões estrela e triângulo e vantagens na indústria.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula")
    ]

    return _ajustar_sequencia_direta(num_aulas, aulas_conteudo,
                                     nome_avaliacao="Avaliação Final: Prova teórico-prática sobre análise de circuitos e grandezas elétricas.",
                                     amb_avaliacao=LAB_ELETRICIDADE)


def _gerar_plano_manutencao_industrial(num_aulas):
    """Gera o plano para Manutenção Elétrica Industrial."""
    aulas_conteudo = [
        ("Apresentação da disciplina, conceitos de confiabilidade e tipos de manutenção (corretiva, preventiva e preditiva).",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Normas de segurança na manutenção elétrica: NR-10, desenergização, bloqueio e etiquetagem (LOTO).",
         "Estudo de Normas Técnicas", "Quadro Branco e Slides", "Sala de Aula"),
        ("Ferramentas de manutenção e instrumentos de medição: alicate amperímetro, terrômetro, fasímetro e analisador de energia.",
         "Aula Expositiva Dialogada", "Quadro Branco e Instrumentos", "Sala de Aula"),
        ("Aula Prática em Bancada: Ensaios de resistência de isolamento em motores elétricos com megômetro.",
         "Aula Prática em Bancada", "Megômetro e Motores Elétricos", LAB_INDUSTRIAIS),
        ("Termografia aplicada à manutenção elétrica preditiva: identificação de pontos quentes em conexões e painéis.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Laboratório: Inspeção termográfica simulada em quadros de distribuição e detecção de sobrecargas.",
         "Aula Prática em Laboratório", "Câmera Termográfica Didática", LAB_INDUSTRIAIS),
        ("Manutenção em transformadores industriais: testes de óleo isolante, relação de espiras (TTR) e limpeza de buchas.",
         "Aula Expositiva Dialogada", "Quadro Branco e Manuais", "Sala de Aula"),
        ("Aula Prática em Bancada: Localização e diagnóstico de falhas em circuitos de comando e força de motores.",
         "Aula Prática em Bancada", "Bancada Didática com Injeção de Falhas", LAB_INDUSTRIAIS),
        ("Planejamento e Controle da Manutenção (PCM): ordem de serviço, histórico de falhas e indicadores (MTBF, MTTR).",
         "Aula Expositiva e Exercícios", "Quadro Branco e Planilhas", "Sala de Aula")
    ]

    return _ajustar_sequencia_direta(num_aulas, aulas_conteudo,
                                     nome_avaliacao="Avaliação Final: Diagnóstico prático de falhas em bancada e avaliação teórica de manutenção.",
                                     amb_avaliacao=LAB_INDUSTRIAIS)


def _gerar_plano_sep(num_aulas):
    """Gera o plano para Sistemas Elétricos de Potência (SEP)."""
    aulas_conteudo = [
        ("Apresentação da disciplina e visão geral da estrutura do SEP (geração, transmissão, subestações e distribuição).",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Segurança em instalações e serviços em SEP: requisitos da NR-10 Complementar e técnicas de trabalho sob tensão.",
         "Estudo de Normas Técnicas", "Quadro Branco e Slides", "Sala de Aula"),
        ("Subestações abaixadoras industriais: arranjos físicos, tipos de barramentos e equipamentos de manobra e corte.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Transformadores de potência: princípios construtivos, sistemas de refrigeração e ensaios normatizados.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Transformadores para Instrumentos (TC e TP): classes de exatidão, conexão de relés e proteção secundária.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Disjuntores de média e alta tensão (SF6 e vácuo) e chaves seccionadoras: dimensionamento e capacidade de interrupção.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Relés de proteção microprocessados: funções ANSI (50/51, 50N/51N, 27, 59) e parametrização de curvas de atuação.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Aula Prática em Software: Simulação de fluxo de potência e coordenação de seletividade da proteção em subestações.",
         "Prática em Software de Simulação", "Microcomputadores e Software SEP", LAB_INFORMATICA),
        ("Procedimentos operacionais de manobra, aterramento temporário e abertura/fechamento de subestações industriais.",
         "Estudo de Casos e Procedimentos", "Quadro Branco e Procedimentos Operacionais", LAB_SEP)
    ]

    return _ajustar_sequencia_direta(num_aulas, aulas_conteudo,
                                     nome_avaliacao="Avaliação Final: Prova teórica e análise de estudos de proteção e coordenação em SEP.",
                                     amb_avaliacao="Sala de Aula")


def _gerar_plano_eficiencia_energetica(num_aulas):
    """Gera o plano para Eficiência Energética."""
    aulas_conteudo = [
        ("Apresentação da disciplina, panorama energético nacional, matriz elétrica e conceitos de conservação de energia.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Estrutura tarifária do setor elétrico: grupo A e B, tarifas verde e azul, demanda contratada e ultrapassagem.",
         "Aula Expositiva e Exercícios", "Quadro Branco e Faturas de Energia", "Sala de Aula"),
        ("Diagnóstico e auditoria energética em plantas industriais: etapas de levantamento, medição e inventário de cargas.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Uso eficiente de motores elétricos: classes de rendimento (IR2, IR3, IR4), superdimensionamento e acionamentos eletrônicos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Eficiência em sistemas de ar comprimido, bombeamento e sistemas térmicos industriais.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Eficiência energética em sistemas luminotécnicos: retrofit com tecnologia LED e controles automáticos de presença/luz natural.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        ("Correção do fator de potência e filtragem de harmônicos: benefícios econômicos e eliminação de multas na fatura.",
         "Aula Expositiva e Exercícios", "Quadro Branco e Calculadora", "Sala de Aula"),
        ("Aula Prática com Analisador de Energia: Medição de grandezas e curvas de carga no laboratório de eficiência.",
         "Aula Prática em Laboratório", "Analisador de Qualidade de Energia", LAB_EFICIENCIA),
        ("Análise de viabilidade econômica de projetos de eficiência: cálculo de Payback simples, VPL e TIR em planilhas.",
         "Aula Prática em Planilhas Técnicas", "Microcomputadores e Planilhas", LAB_INFORMATICA)
    ]

    return _ajustar_sequencia_direta(num_aulas, aulas_conteudo,
                                     nome_avaliacao="Avaliação Final: Elaboração e apresentação de plano de eficiência energética industrial.",
                                     amb_avaliacao=LAB_INFORMATICA)


def _gerar_plano_projetos_generico(disciplina, num_aulas):
    """Gera plano para qualquer outra disciplina de projetos."""
    labs = obter_laboratorios_disciplina(disciplina)
    lab_pc = labs[0] if labs else LAB_INFORMATICA

    teoricas = [
        (f"Apresentação da disciplina, escopo e requisitos técnicos para elaboração de {disciplina}.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        (f"Leitura, interpretação de especificações e levantamento de necessidades de campo para o projeto.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        (f"Normas técnicas regulamentadoras, simbologia e padronização aplicada a {disciplina}.",
         "Estudo de Normas Técnicas", "Quadro Branco e Apostila", "Sala de Aula"),
        (f"Metodologias e critérios de dimensionamento técnico dos componentes do projeto.",
         "Aula Expositiva e Cálculos Técnicos", "Quadro Branco e Calculadora", "Sala de Aula"),
        (f"Especificação técnica de materiais, equipamentos e dispositivos do sistema projetado.",
         "Aula Expositiva Dialogada", "Quadro Branco e Catálogos Técnicos", "Sala de Aula"),
        (f"Critérios de segurança, confiabilidade operacional e proteção dos circuitos e estruturas.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula"),
        (f"Metodologia de documentação técnica: quadros de cargas, memoriais descritivos e estimativa de custos.",
         "Aula Expositiva Dialogada", "Quadro Branco e Slides", "Sala de Aula")
    ]

    praticas_projeto = [
        (f"Elaboração de Projeto (Etapa 1): Definição de premissas, layout inicial e setorização no software CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", lab_pc),
        (f"Elaboração de Projeto (Etapa 2): Lançamento dos pontos técnicos, circuitos e encaminhamentos em planta.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", lab_pc),
        (f"Elaboração de Projeto (Etapa 3): Dimensionamento técnico em planilhas e detalhamento dos componentes em CAD.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", lab_pc),
        (f"Elaboração de Projeto (Etapa 4): Elaboração dos diagramas esquemáticos e detalhes construtivos em prancha.",
         "Desenvolvimento de Projeto em CAD", "Microcomputadores e Software CAD", lab_pc),
        (f"Elaboração de Projeto (Etapa 5): Consolidação dos quadros técnicos, especificações e lista quantitativa de materiais.",
         "Documentação Técnica de Projeto", "Microcomputadores e Processador de Texto", lab_pc),
        (f"Elaboração de Projeto (Etapa 6): Elaboração do memorial descritivo completo e estimativa de custos do projeto.",
         "Documentação Técnica de Projeto", "Microcomputadores e Processador de Texto", lab_pc),
        (f"Elaboração de Projeto (Etapa 7): Compatibilização de interferências, revisão geral das pranchas e fechamento do projeto.",
         "Revisão Técnica de Projeto", "Microcomputadores e Software CAD", lab_pc)
    ]

    return _combinar_aulas(num_aulas, teoricas, praticas_projeto,
                           nome_avaliacao=f"Avaliação Final: Entrega e apresentação técnica do projeto desenvolvido em {disciplina}.",
                           amb_avaliacao=lab_pc)


def _gerar_plano_dinamico_pct(disciplina, num_aulas, conhecimentos_pct=None, laboratorios=None):
    """
    Gera dinamicamente aulas para qualquer disciplina do Plano de Curso:
    - Enriquecimento pedagógico (no máximo 1 a 2 linhas, sem assuntos vagos);
    - Intercala aulas teóricas com aulas práticas de laboratório com nome oficial do PCT enviado pelo usuário;
    - Avaliação e recuperação no encerramento.
    """
    conhecimentos_pct = conhecimentos_pct or []
    labs_disponiveis = laboratorios if (laboratorios and len(laboratorios) > 0) else obter_laboratorios_disciplina(disciplina)
    lab_pratica = labs_disponiveis[0] if labs_disponiveis else LAB_INFORMATICA

    # Limpeza e filtragem de tópicos válidos do plano de curso
    topicos_limpos = []
    for c in conhecimentos_pct:
        c_str = re.sub(r'^\d+(\.\d+)*\s*', '', c).strip()
        if len(c_str) > 4 and not c_str.lower().endswith((' e', ' de', ' por', ' em', ' contra')):
            topicos_limpos.append(c_str)

    num_meio = max(1, num_aulas - 3)
    itens_selecionados = []

    if topicos_limpos:
        for i in range(num_meio):
            idx = int(i * len(topicos_limpos) / num_meio)
            itens_selecionados.append(topicos_limpos[idx])
    else:
        itens_selecionados = [
            f"Princípios teóricos e fundamentos conceituais aplicados a {disciplina}.",
            f"Normas técnicas regulamentadoras, simbologia e procedimentos operacionais.",
            f"Arquitetura, componentes principais e características de funcionamento do sistema.",
            f"Critérios de especificação, seleção de equipamentos e grandezas envolvidas.",
            f"Métodos de dimensionamento, cálculo técnico e parametrização de grandezas.",
            f"Diagnóstico de anomalias, análise de falhas operacionais e manutenção.",
            f"Aplicações industriais típicas, eficiência operacional e estudo de casos práticos."
        ]
        while len(itens_selecionados) < num_meio:
            itens_selecionados.append(f"Aprofundamento técnico e análise aplicada de {disciplina}.")

    aulas_meio = []
    for i, topico in enumerate(itens_selecionados[:num_meio]):
        if i > 0 and (i % 3 == 0 or any(k in topico.lower() for k in ['pratica', 'ensaio', 'medicao', 'montagem', 'circuito', 'software'])):
            conteudo = f"Aula Prática em Laboratório / Bancada: Ensaios aplicados e análise funcional de {topico.lower()}."
            aulas_meio.append((
                conteudo,
                "Aula Prática em Laboratório",
                "Bancada Didática e Instrumentos",
                lab_pratica
            ))
        else:
            conteudo = f"Estudo e aplicação de {topico.lower()}: conceitos fundamentais, normas e aspectos operacionais."
            aulas_meio.append((
                conteudo,
                "Aula Expositiva Dialogada",
                "Quadro Branco e Slides",
                "Sala de Aula"
            ))

    aulas = []
    aulas.append({
        "conhecimento": f"Apresentação da disciplina de {disciplina}, metodologia pedagógica e critérios de avaliação.",
        "estrategia": "Aula Expositiva Dialogada",
        "recursos": "Quadro Branco e Slides",
        "ambiente": "Sala de Aula"
    })

    for c, est, rec, amb in aulas_meio:
        aulas.append({
            "conhecimento": c,
            "estrategia": est,
            "recursos": rec,
            "ambiente": amb
        })

    if len(aulas) < num_aulas:
        aulas.append({
            "conhecimento": f"Avaliação Final: Atividade avaliativa teórica e prática sobre os conteúdos ministrados.",
            "estrategia": "Atividade Avaliativa",
            "recursos": "Prova Escrita e Prática",
            "ambiente": lab_pratica
        })

    if len(aulas) < num_aulas:
        aulas.append({
            "conhecimento": "Recuperação: Revisão pedagógica dos tópicos essenciais e avaliação complementar.",
            "estrategia": "Atividade Avaliativa",
            "recursos": "Prova Escrita",
            "ambiente": "Sala de Aula"
        })

    return aulas[:num_aulas]


# ==============================================================================
# FUNÇÕES DE APOIO PARA MONTAGEM E BALANCEAMENTO DAS AULAS
# ==============================================================================

def _combinar_aulas(num_aulas, teoricas, praticas, nome_avaliacao, amb_avaliacao):
    """Combina aulas teóricas iniciais com etapas práticas de projeto."""
    aulas = []
    num_uteis = max(1, num_aulas - 2)

    if num_aulas >= 12:
        qtd_teoricas = min(len(teoricas), max(5, int(num_uteis * 0.45)))
    else:
        qtd_teoricas = max(2, int(num_uteis * 0.5))

    qtd_praticas = max(1, num_uteis - qtd_teoricas)

    teoricas_sel = []
    for i in range(qtd_teoricas):
        idx = int(i * len(teoricas) / qtd_teoricas)
        teoricas_sel.append(teoricas[idx])

    praticas_sel = []
    for i in range(qtd_praticas):
        idx = int(i * len(praticas) / qtd_praticas)
        praticas_sel.append(praticas[idx])

    for c, est, rec, amb in (teoricas_sel + praticas_sel):
        aulas.append({
            "conhecimento": c,
            "estrategia": est,
            "recursos": rec,
            "ambiente": amb
        })

    if num_aulas > 1:
        aulas.append({
            "conhecimento": nome_avaliacao,
            "estrategia": "Atividade Avaliativa",
            "recursos": "Entrega do Projeto / Prova Escrita",
            "ambiente": amb_avaliacao
        })

    if num_aulas > 2:
        aulas.append({
            "conhecimento": "Recuperação: Revisão pedagógica dos critérios técnicos de projeto e complementação avaliativa.",
            "estrategia": "Atividade Avaliativa",
            "recursos": "Prova Escrita",
            "ambiente": "Sala de Aula"
        })

    return aulas[:num_aulas]


def _ajustar_sequencia_direta(num_aulas, aulas_conteudo, nome_avaliacao, amb_avaliacao):
    """Ajusta uma lista linear de aulas teóricas/práticas para caber exatamente em num_aulas."""
    aulas = []
    num_uteis = max(1, num_aulas - 2)

    selecionadas = []
    for i in range(num_uteis):
        idx = int(i * len(aulas_conteudo) / num_uteis)
        selecionadas.append(aulas_conteudo[idx])

    for c, est, rec, amb in selecionadas:
        aulas.append({
            "conhecimento": c,
            "estrategia": est,
            "recursos": rec,
            "ambiente": amb
        })

    if num_aulas > 1:
        aulas.append({
            "conhecimento": nome_avaliacao,
            "estrategia": "Atividade Avaliativa",
            "recursos": "Prova Escrita e Prática",
            "ambiente": amb_avaliacao
        })

    if num_aulas > 2:
        aulas.append({
            "conhecimento": "Recuperação: Revisão pedagógica dos conceitos essenciais e atividade avaliativa complementar.",
            "estrategia": "Atividade Avaliativa",
            "recursos": "Prova Escrita",
            "ambiente": "Sala de Aula"
        })

    return aulas[:num_aulas]


# ==============================================================================
# FUNÇÃO PRINCIPAL DE ENTRADA DO AI SERVICE
# ==============================================================================

def gerar_plano_com_ia(disciplina, curso, num_aulas, carga_horaria, horas_aula, provedor="gemini", api_key="", ementa_texto="", conhecimentos_pct=None, laboratorios=None):
    """
    Coordena a geração com IA:
    1. Se houver chave Gemini, utiliza a API do Gemini com prompt altamente contextualizado e estruturado.
    2. Se não houver chave ou falhar, utiliza o motor contextualizado oficial SENAI (Built-in AI).
    Garante que os tópicos tenham contextualização rica e resumida (máximo 1 a 2 linhas),
    mesclando teoria e práticas de projeto/laboratório, com os nomes oficiais dos laboratórios do Plano de Curso.
    """
    api_key = api_key.strip() or carregar_chave_env()
    conhecimentos_pct = conhecimentos_pct or []

    disc_norm = normalizar_texto(disciplina)
    is_projeto = any(k in disc_norm for k in ['projeto', 'desenho tecnico'])
    labs_recomendados = laboratorios if (laboratorios and len(laboratorios) > 0) else obter_laboratorios_disciplina(disciplina)
    lista_labs_str = ", ".join([f'"{lab}"' for lab in labs_recomendados])

    # Se tiver chave de API do Gemini configurada
    if api_key:
        lista_conhecimentos_str = "\n".join([f"- {c}" for c in conhecimentos_pct]) if conhecimentos_pct else ementa_texto[:3000]

        instrucao_especifica = ""
        if is_projeto:
            instrucao_especifica = f"""
DIRETRIZ OBRIGATÓRIA PARA ESTA DISCIPLINA DE PROJETOS:
- As primeiras aulas (~8 a 10 primeiras aulas se carga horária permitir, ou cerca de 40% a 50% das aulas úteis) DEVEM conter toda a parte teórica: normas regulamentadoras, conceitos, cálculos técnicos, dimensionamento e critérios operacionais.
- As aulas intermediárias seguintes DEVEM ser as etapas práticas da elaboração do projeto técnico.
- Para as etapas de elaboração de projeto: use Estratégia "Desenvolvimento de Projeto em CAD" ou "Desenvolvimento Prático Orientado", Recursos adequados e para o ambiente use estritamente: "Laboratório de Informática" ou laboratórios oficiais do curso: {lista_labs_str}.
"""
        else:
            instrucao_especifica = f"""
DIRETRIZ OBRIGATÓRIA PARA ESTA DISCIPLINA:
- Mescle aulas teóricas com aulas práticas de laboratório, bancada didática ou medições/ensaios.
- Para aulas práticas: use Estratégia "Aula Prática em Bancada / Laboratório", Recursos condizentes com o laboratório, e no campo ambiente utilize ESTRITAMENTE os laboratórios do Plano de Curso enviado pelo usuário: {lista_labs_str}.
"""

        prompt = f"""
Você é um Coordenador Pedagógico e Docente Especialista do SENAI/RN (Centro de Educação e Tecnologias Ítalo Bologna).
Sua tarefa é montar o cronograma oficial de aulas do SENAI:
- Disciplina: {disciplina}
- Curso: {curso or "Técnico do SENAI"}
- Carga Horária Total: {carga_horaria}h ({horas_aula}h por aula)
- Quantidade EXATA de aulas a gerar: {num_aulas} aulas

CONHECIMENTOS DA DISCIPLINA NO PLANO DE CURSO ENVIADO PELO USUÁRIO:
\"\"\"
{lista_conhecimentos_str}
\"\"\"

LABORATÓRIOS OFICIAIS DO PLANO DE CURSO PARA ESTA DISCIPLINA:
{lista_labs_str}

REGRAS DE CONTEXTUALIZAÇÃO PEDAGÓGICA (MUITO IMPORTANTE):
1. NUNCA gere tópicos vagos ou palavras isoladas como "Tipos", "Backup", "Normas" ou "Componentes".
2. Cada aula no campo "conhecimento" DEVE ser pedagogicamente contextualizada em NO MÁXIMO 1 OU 2 LINHAS curtas e objetivas, ideais para caber perfeitamente na tabela do plano de aula oficial.
3. REGRA RIGOROSA PARA O CAMPO 'ambiente':
   - Quando forem aulas teóricas expositivas: utilize SEMPRE "Sala de Aula". NUNCA use números de sala (como Sala 10).
   - Quando forem utilizadas aulas práticas ou etapas de projeto em laboratório: utilize RIGOROSAMENTE os nomes dos laboratórios presentes no Plano de Curso do SENAI enviado pelo usuário ({lista_labs_str}).
   - NUNCA utilize termos genéricos como apenas "Laboratório", "Lab" ou "Laboratório Técnico".
4. {instrucao_especifica}
5. Estrutura das aulas nos extremos:
   - Aula 1: Apresentação da Disciplina, cronograma pedagógico e introdução ao conteúdo.
   - Penúltima aula (Aula {num_aulas - 1}): "Avaliação Final" com contextualização do formato de avaliação.
   - Última aula (Aula {num_aulas}): "Recuperação: Revisão de conteúdo e atividade avaliativa complementar."

Retorne EXATAMENTE {num_aulas} itens no formato JSON puro (sem markdown extra):
[
  {{
    "conhecimento": "Texto contextualizado da aula (no máximo 1 ou 2 linhas)",
    "estrategia": "Aula Expositiva Dialogada",
    "recursos": "Quadro Branco e Slides",
    "ambiente": "Sala de Aula"
  }},
  ...
]
"""
        try:
            texto_resposta = chamar_gemini(api_key, prompt)
            aulas_ia = parsear_resposta_json(texto_resposta, num_aulas)
            if len(aulas_ia) == num_aulas:
                return aulas_ia, "Conteúdos gerados via Google Gemini com contextualização teórica e laboratórios do Plano de Curso."
        except Exception as e:
            print(f"Erro chamada Gemini: {e}")

    # Fallback / Motor Pedagógico SENAI Integrado
    aulas_geradas = gerar_conteudos_contextualizados(
        disciplina=disciplina,
        num_aulas=num_aulas,
        carga_horaria=carga_horaria,
        horas_aula=horas_aula,
        conhecimentos_pct=conhecimentos_pct,
        laboratorios=labs_recomendados
    )
    return aulas_geradas, "Conteúdos gerados pelo motor pedagógico contextualizado SENAI (com laboratórios do Plano de Curso)."

