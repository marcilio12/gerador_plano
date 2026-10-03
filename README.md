# Gerador de Plano de Aula — SENAI

Sistema web desenvolvido em **Python (Flask)** para automatizar a elaboração de planos de aula e planejamento pedagógico para docentes do **SENAI** (Centro de Educação e Tecnologias Ítalo Bologna — Mossoró/RN).

---

## 🚀 Principais Funcionalidades

- **Análise Dinâmica do Plano de Curso (PDF)**:
  - O sistema lê em tempo real qualquer arquivo de Plano de Curso (PCT) enviado pelo professor via upload.
  - Extrai automaticamente o **Nome do Curso**, a lista de **Unidades Curriculares (Disciplinas)**, **Módulos**, **Carga Horária**, **Competência Geral / Objetivo Geral**, **Unidade de Competência** e os **Laboratórios Oficiais** específicos do curso e da disciplina.
  - Funciona dinamicamente com qualquer curso técnico (*Eletromecânica, Eletrotécnica, Mecânica, Automação, etc.*) e futuras atualizações curriculares.

- **Cálculo Inteligente de Calendário & Feriados**:
  - Calcula automaticamente as datas de início e término das aulas.
  - Pula fins de semana e considera todos os **feriados nacionais**, **estaduais do RN** e **municipais de Mossoró/RN** (Abolição de Mossoró, Santa Luzia, Santo Antônio, etc.).

- **Inteligência Pedagógica Contextualizada**:
  - Distribuição pedagógica equilibrada entre aulas teóricas e práticas em laboratório.
  - Utilização estrita dos laboratórios oficiais citados no Plano de Curso enviado (ex.: *Laboratório de Usinagem, Laboratório de Metrologia, Laboratório de Soldagem, Laboratório de Informática, etc.*).
  - Aulas teóricas padronizadas com `"Sala de Aula"`.
  - Integração com a API do **Google Gemini** para enriquecimento e contextualização dos conteúdos formativos, com fallback para o motor pedagógico integrado.

- **Geração e Edição de Documentos Oficiais**:
  - Tela de edição e pré-visualização completa antes do fechamento.
  - Exportação em formato `.docx` e conversão para `.pdf` com formatação e diagramação 100% fiéis ao modelo institucional do SENAI.

- **Autenticação Oficial Google**:
  - Login seguro com conta institucional ou pessoal via **Google OAuth 2.0** e **Google Identity Services (One Tap)** em janela modal / pop-up.

---

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python 3, Flask
- **Manipulação de Documentos**: `python-docx`, `pdfplumber`, `docx2pdf`
- **Calendário & Feriados**: `holidays`
- **Inteligência Artificial**: Google Gemini API (`google-generativeai` / REST)
- **Autenticação**: Google OAuth 2.0 / Google Identity Services
- **Frontend**: HTML5, Bootstrap 5, Bootstrap Icons, JavaScript moderno

---

## 📦 Instalação e Execução

### 1. Clonar o Repositório
```bash
git clone https://github.com/marcilio12/gerador_plano.git
cd gerador_plano
```

### 2. Criar Ambiente Virtual (opcional, recomendado)
```bash
python -m venv venv
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate
```

### 3. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto com as suas credenciais:
```env
GOOGLE_CLIENT_ID=seu_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=sua_chave_secreta_google
GEMINI_API_KEY=sua_chave_api_gemini
SECRET_KEY=chave_secreta_flask
```

### 5. Iniciar a Aplicação
```bash
python app.py
```
Acesse a aplicação no navegador em: `http://localhost:5000`

---

## 📄 Licença
Desenvolvido para apoio às atividades pedagógicas do SENAI/RN.
