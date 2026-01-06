import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== INICIALIZAÇÃO DE ESTADO ====================
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

        # Definir o schema esperado para a tabela 'processos'
        expected_processos_column_names = [
            'id', 'numero', 'rt', 'requerente', 'analista', 'uso', 
            'tipologia', 'area', 'data_protocolo', 'status', 'data_cadastro'
        ]

        schema_outdated = False

        # Verificar se a tabela 'processos' existe
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processos'")
        table_exists = c.fetchone()

        if table_exists:
            c.execute("PRAGMA table_info(processos)")
            current_columns_info = c.fetchall()
            current_column_names = [col[1] for col in current_columns_info]

            # Verifica se o conjunto de colunas atuais é EX

