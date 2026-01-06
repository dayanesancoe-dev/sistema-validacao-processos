import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os
import yaml # Para gerenciar as credenciais de forma segura
from yaml.loader import SafeLoader # Para carregar o YAML de forma segura

# Tenta importar pandas e plotly.express, com fallback para evitar crash
try:
    import pandas as pd
    import plotly.express as px
    plotly_available = True
except ImportError:
    pd = None
    px = None
    plotly_available = False
    st.warning("⚠️ As bibliotecas 'pandas' e 'plotly' não foram encontradas. As funcionalidades de gráficos e algumas análises podem não estar disponíveis. Verifique seu 'requirements.txt'.")

# Importa o autenticador
try:
    import streamlit_authenticator as stauth
    authenticator_available = True
except ImportError:
    stauth = None
    authenticator_available = False
    st.error("❌ A biblioteca 'streamlit-authenticator' não foi encontrada. O sistema de login não funcionará. Verifique seu 'requirements.txt'.")


st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== CONFIGURAÇÃO DE LOGIN ====================
# Carrega as credenciais do arquivo config.yaml
# Para produção, este arquivo deve ser armazenado de forma segura (ex: Streamlit Secrets)
# Exemplo de config.yaml:
# credentials:
#   usernames:
#     jsmith:
#       email: jsmith@example.com
#       name: John Smith
#       password: abc
#     rbriggs:
#       email: rbriggs@example.com
#       name: Rebecca Briggs
#       password: def
# cookie:
#   expiry_days: 30
#   key: some_secret_key # Mude para uma chave secreta real
#   name: streamlit_cookie
# preauthorized:
#   emails:
#     - rbriggs@example.com

# --- Início do bloco de autenticação ---
if authenticator_available:
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        config['preauthorized']
    )

    name, authentication_status, username = authenticator.login('Login', 'main')

    if authentication_status == False:
        st.error('Nome de usuário/senha incorretos')
        st.stop() # Para a execução do restante do app
    elif authentication_status == None:
        st.warning('Por favor, insira seu nome de usuário e senha')
        st.stop() # Para a execução do restante do app
    elif authentication_status:
        # Usuário logado com sucesso
        st.sidebar.write(f'Bem-vindo, *{name}*')
        authenticator.logout('Sair', 'sidebar')
        # Define o nome do usuário logado na session_state para uso posterior
        st.session_state['logged_in_user'] = name
else:
    st.error("Sistema de login desativado devido à falta da biblioteca 'streamlit-authenticator'.")
    st.stop() # Para a execução do restante do app
# --- Fim do bloco de autenticação ---


# ==================== INICIALIZAÇÃO DE ESTADO (APÓS LOGIN) ====================
# Garante que a API Key esteja sempre inicializada
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''

# Flag para forçar rerun após reset do banco
if 'db_reset_needed_rerun' not in st.session_state:
    st.session_state['db_reset_needed_rerun'] = False

if st.session_state['db_reset_needed_rerun']:
    st.session_state['db_reset_needed_rerun'] = False
    st.experimental_rerun()

# ==================== BANCO DE DADOS ====================

def reset_database():
    """Reseta o banco de dados, removendo o arquivo e limpando o cache."""
    try:
        if os.path.exists('processos.db'):
            os.remove('processos.db')
        st.cache_resource.clear() # Limpa o cache para forçar a recriação da conexão
        st.session_state['db_reset_needed_rerun'] = True # Define a flag para forçar rerun
        st.success("✅ Banco de dados resetado com sucesso! A página será recarregada.")
        st.experimental_rerun() # Força o rerun
    except Exception as e:
        st.error(f"❌ Erro ao resetar o banco de dados: {str(e)}")
        return None

@st.cache_resource
def init_db():
    """Inicializa o banco de dados, criando tabelas se não existirem ou se o schema estiver desatualizado."""
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()

        # Verificar se a tabela 'processos' existe
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processos'")
        table_exists = c.fetchone()

        # Definir o schema esperado para a tabela 'processos'
        expected_processos_column_names = [
            'id', 'numero', 'rt', 'requerente', 'analista', 'uso', 
            'tipologia', 'area', 'data_protocolo', 'status', 'data_cadastro'
        ]

        schema_outdated = False

        if table_exists:
            c.execute("PRAGMA table_info(processos)")
            current_columns_info = c.fetchall()
            current_column_names = [col[1] for col in current_columns_info]

            # Verifica se o conjunto de colunas atuais é EXATAMENTE igual ao esperado
            if not (set(expected_processos_column_names) == set(current_column_names) and 
                    len(expected_processos_column_names) == len(current_column_names)):
                schema_outdated = True
        else:
            schema_outdated = True # Tabela não existe, então precisa ser criada

        if schema_outdated:
            st.warning("⚠️ Detectada estrutura de banco de dados antiga ou inconsistente. Recriando tabelas...")
            c.execute('DROP TABLE IF EXISTS tramitacao')
            c.execute('DROP TABLE IF EXISTS analises')
            c.execute('DROP TABLE IF EXISTS processos')
            conn.commit() # Commit das drops

            # Recriar tabela 'processos'
            c.execute('''CREATE TABLE processos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE NOT NULL,
                rt TEXT NOT NULL,
                requerente TEXT NOT NULL,
                analista TEXT NOT NULL,
                uso TEXT NOT NULL,
                tipologia TEXT NOT NULL,
                area REAL NOT NULL,
                data_protocolo TEXT NOT NULL,
                status TEXT DEFAULT 'Protocolado',
                data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit() # Commit da criação da tabela processos

        # Criar tabela 'analises' (sempre garante que exista)
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        conn.commit()

        # Criar tabela 'tramitacao' (sempre garante que exista)
        c.execute('''CREATE TABLE IF NOT EXISTS tramitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            setor TEXT NOT NULL,
            data_entrada TEXT NOT NULL,
            data_saida TEXT,
            observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        conn.commit()

        return conn
    except Exception as e:
        st.error(f"❌ Erro ao inicializar o banco de dados: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES CRUD (PROCESSOS) ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    """Cadastra um novo processo no banco de dados."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO processos 
                    (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo))
        conn.commit()
        return True, "✅ Processo cadastrado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "❌ Erro: Número de processo já existe!"
    except Exception as e:
        return False, f"❌ Erro ao cadastrar: {str(e)}"

def listar():
    """Lista todos os processos cadastrados."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar processos: {str(e)}")
        return []

def buscar_por_numero(numero):
    """Busca um processo pelo número."""
    if not conn: return None
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (numero,))
        return c.fetchone()
    except Exception as e:
        st.error(f"Erro ao buscar processo: {str(e)}")
        return None

def atualizar(pid, numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    """Atualiza os dados de um processo existente."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE processos 
                    SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=?
                    WHERE id=?''',
                 (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo, pid))
        conn.commit()
        return True, "✅ Processo atualizado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "❌ Erro: Número de processo já existe!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar: {str(e)}"

def deletar(pid):
    """Deleta um processo e suas tramitações e análises associadas."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        # Deleta tramitações e análises primeiro devido às chaves estrangeiras
        c.execute('DELETE FROM tramitacao WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True, "✅ Processo deletado com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao deletar: {str(e)}"

def atualizar_status(pid, novo_status):
    """Atualiza o status de um processo."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('UPDATE processos SET status = ? WHERE id = ?', (novo_status, pid))
        conn.commit()
        return True, "✅ Status atualizado!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar status: {str(e)}"

# ==================== FUNÇÕES CRUD (TRAMITAÇÃO) ====================

def registrar_tramitacao(processo_id, setor, data_entrada, data_saida=None, observacao=""):
    """Registra uma nova movimentação de tramitação para um processo."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        # Fecha a tramitação anterior (se houver) com a data de entrada da nova
        c.execute('''UPDATE tramitacao
                    SET data_saida = ?
                    WHERE processo_id = ? AND data_saida IS NULL''',
                 (data_entrada, processo_id))

        c.execute('''INSERT INTO tramitacao
                    (processo_id, setor, data_entrada, data_saida, observacao)
                    VALUES (?, ?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada, data_saida, observacao))
        conn.commit()
        return True, "✅ Tramitação registrada com sucesso!"
    except Exception as e:
        return False, f"❌ Erro ao registrar tramitação: {str(e)}"

def listar_tramitacao(processo_id):
    """Lista as tramitações de um processo específico."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM tramitacao WHERE processo_id = ? ORDER BY data_entrada DESC', (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar tramitações: {str(e)}")
        return []

def atualizar_tramitacao(tid, setor, data_entrada, data_saida, observacao):
    """Atualiza uma movimentação de tramitação existente."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''UPDATE tramitacao
                    SET setor=?, data_entrada=?, data_saida=?, observacao=?
                    WHERE id=?''',
                 (setor, data_entrada, data_saida, observacao, tid))
        conn.commit()
        return True, "✅ Movimentação atualizada!"
    except Exception as e:
        return False, f"❌ Erro ao atualizar movimentação: {str(e)}"

def deletar_tramitacao(tid):
    """Deleta uma movimentação de tramitação."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('DELETE FROM tramitacao WHERE id = ?', (tid,))
        conn.commit()
        return True, "✅ Movimentação deletada!"
    except Exception as e:
        return False, f"❌ Erro ao deletar movimentação: {str(e)}"

# ==================== FUNÇÕES CRUD (ANÁLISES) ====================

def salvar_analise(processo_id, resultado, status):
    """Salva o resultado de uma análise no banco de dados."""
    if not conn: return False, "❌ Erro de conexão com o banco!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO analises
                    (processo_id, resultado, status)
                    VALUES (?, ?, ?)''',
                 (processo_id, resultado, status))
        conn.commit()
        return True, "✅ Análise salva!"
    except Exception as e:
        return False, f"❌ Erro ao salvar análise: {str(e)}"

def listar_analises(processo_id):
    """Lista as análises de um processo específico."""
    if not conn: return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY data_analise DESC', (processo_id,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar análises: {str(e)}")
        return []

# ==================== CONFIGURAÇÕES GERAIS ====================

# Opções para os campos de seleção
usos_options = ["Unifamiliar", "Multifamiliar", "Serviços", "Comércio Varejista", "Comércio Atacadista", "Indústria", "Misto", "Sem destinação específica"]
tipologias_options = ["Aprovação Inicial", "Levantamento Existente", "Modificação de Projeto", "Regularização", "Misto", "RIU", "ERB", "As Built"]
status_kanban = ["Protocolado", "Em Análise", "Aguardando Correções", "Aprovado", "Reprovado"]
setores_tramitacao = ["Protocolo", "Requerente", "Analista", "Fiscalização", "Parecer Externo", "Emissão de Alvará", "Arquivo"]

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("⚙️ Configurações")
    st.markdown("---")

    # Entrada da API Key do Gemini
    st.subheader("🔑 API Key Google Gemini")
    st.session_state['api_key'] = st.text_input("Insira sua API Key", type="password", value=st.session_state['api_key'])
    if st.session_state['api_key']:
        try:
            genai.configure(api_key=st.session_state['api_key'])
            st.success("API Key configurada!")
        except Exception as e:
            st.error(f"Erro ao configurar API Key: {str(e)}")
    else:
        st.warning("Por favor, insira sua API Key do Google Gemini para usar a análise de PDF.")

    st.markdown("---")
    if st.button("🔄 Resetar Banco de Dados", help="Apaga todos os dados e recria as tabelas."):
        reset_database()

    st.markdown("---")
    st.markdown("### ℹ️ Sobre")
    st.info("Este sistema auxilia na validação e gerenciamento de processos de liberação de alvarás.")

# ==================== ABAS PRINCIPAIS ====================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 Analisar", "📈 Gráficos"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("➕ Cadastro de Novo Processo")

    with st.form("form_cadastro_processo"):
        st.subheader("Dados do Processo")
        numero = st.text_input("Número do Processo", help="Ex: 12345/2024")
        rt = st.text_input("Responsável Técnico (RT)")
        requerente = st.text_input("Requerente")
        analista = st.text_input("Analista Responsável")

        col1, col2 = st.columns(2)
        with col1:
            uso = st

