import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io
# Configuração da página
st.set_page_config(
    page_title="Sistema de Validação de Processos",
    page_icon="🏛️",
    layout="wide"
)
# Título
st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem** — Liberação de Alvarás de Construção")
# Inicializar banco de dados
@st.cache_resource
def init_db():
    conn = sqlite3.connect('processos.db', check_same_thread=False)
    cursor = conn.cursor()
    # Criar tabelas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_processo TEXT UNIQUE NOT NULL,
            requerente TEXT NOT NULL,
            rt TEXT NOT NULL,
            analista TEXT NOT NULL,
            uso TEXT NOT NULL,
            area_total REAL NOT NULL,
            estatus TEXT DEFAULT 'Em análise',
            data_protocolo TEXT DEFAULT CURRENT_TIMESTAMP,
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS legislacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            descricao TEXT,
            pdf_nome TEXT,
            pdf_conteudo BLOB,
            data_criacao TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regras_legislacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            legislacao_id INTEGER NOT NULL,
            artigo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            campo_validacao TEXT NOT NULL,
            operador TEXT NOT NULL,
            valor_referencia REAL NOT NULL,
            mensagem_erro TEXT,
            FOREIGN KEY (legislacao_id) REFERENCES legislacoes(id)
        )
    ''')
    conn.commit()
    return conn, cursor
conn, cursor = init_db()
# Funções do sistema
def cadastrar_processo(numero, requerente, rt, analista, uso, area):
    try:
        cursor.execute('''
            INSERT INTO processos (numero_processo, requerente, rt, analista, uso, area_total)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (numero, requerente, rt, analista, uso, area))
        conn.commit()
        st.success(f"✅ Processo {numero} cadastrado com sucesso!")
        return True
    except sqlite3.IntegrityError:
        st.error(f"❌ Processo {numero} já existe!")
        return False
def listar_processos():
    cursor.execute('SELECT id, numero_processo, requerente, rt, uso, area_total, estatus FROM processos')
    processos = cursor.fetchall()
    return processos
def cadastrar_legislacao(nome, descricao, pdf_file=None):
    try:
        if pdf_file:
            pdf_bytes = pdf_file.read()
            pdf_nome = pdf_file.name
            cursor.execute('''
                INSERT INTO legislacoes (nome, descricao, pdf_nome, pdf_conteudo)
                VALUES (?, ?, ?, ?)
            ''', (nome, descricao, pdf_nome, pdf_bytes))
        else:
            cursor.execute('''
                INSERT INTO legislacoes (nome, descricao)
                VALUES (?, ?)
            ''', (nome, descricao))
        conn.commit()
        st.success(f"✅ Legislação '{nome}' cadastrada com sucesso!")
        return True
    except sqlite3.IntegrityError:
        st.error(f"❌ Legislação '{nome}' já existe!")
        return False
def listar_legislacoes():
    cursor.execute('SELECT id, nome, descricao FROM legislacoes')
    return cursor.fetchall()
def adicionar_regra(leg_id, artigo, descricao, campo, operador, valor, mensagem):
    try:
        cursor.execute('''
            INSERT INTO regras_legislacao
            (legislacao_id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (leg_id, artigo, descricao, campo, operador, valor, mensagem))
        conn.commit()
        st.success(f"✅ Regra '{artigo}' adicionada com sucesso!")
        return True
    except Exception as e:
        st.error(f"❌ Erro ao adicionar regra: {str(e)}")
        return False
def listar_regras_legislacao(legislacao_id):
    cursor.execute('''
        SELECT id, artigo, descricao, campo_validacao, operador, valor_referencia
        FROM regras_legislacao
        WHERE legislacao_id = ?
    ''', (legislacao_id,))
    return cursor.fetchall()
def validar_processo(processo_id, legislacao_id):
    cursor.execute('SELECT * FROM processos WHERE id = ?', (processo_id,))
    processo = cursor.fetchone()
    if not processo:
        return None
    cursor.execute('''
        SELECT id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro
        FROM regras_legislacao
        WHERE legislacao_id = ?
    ''', (legislacao_id,))
    regras = cursor.fetchall()
    conformidades = []
    violacoes = []
    # Mapeamento de campos
    campos_processo = {
        'numero_processo': processo[1],
        'requerente': processo[2],
        'rt': processo[3],
        'analista': processo[4],
        'uso': processo[5],
        'area_total': processo[6],
        'estatus': processo[7]
    }
    for regra in regras:
        campo = regra[3]
        operador = regra[4]
        valor_ref = regra[5]
        if campo not in campos_processo:
            continue
        valor_campo = campos_processo[campo]
        # Validar
        resultado = False
        if operador == '>=':
            resultado = float(valor_campo) >= float(valor_ref)
        elif operador == '<=':
            resultado = float(valor_campo) <= float(valor_ref)
        elif operador == '>':
            resultado = float(valor_campo) > float(valor_ref)
        elif operador == '<':
            resultado = float(valor_campo) < float(valor_ref)
        elif operador == '==':
            resultado = str(valor_campo) == str(valor_ref)
        elif operador == '!=':
            resultado = str(valor_campo) != str(valor_ref)
        if resultado:
            conformidades.append({
                'artigo': regra[1],
                'descricao': regra[2],
                'id': regra[0]
            })
        else:
            violacoes.append({
                'artigo': regra[1],
                'descricao': regra[2],
                'campo': campo,
                'valor_esperado': f"{operador} {valor_ref}",
                'valor_encontrado': valor_campo,
                'mensagem': regra[6],
                'id': regra[0]
            })
    return {
        'numero_processo': processo[1],
        'requerente': processo[2],
        'total_regras': len(regras),
        'total_conformidades': len(conformidades),
        'total_violacoes': len(violacoes),
        'conformidades': conformidades,
        'violacoes': violacoes
    }
# Menu principal com abas
tab1, tab2, tab3, tab4 = st.tabs(["📝 Processos", "📚 Legislações", "✅ Validar", "📊 Relatórios"])
# ABA 1: PROCESSOS
with tab1:
    st.header("Gerenciar Processos")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("➕ Cadastrar Novo Processo")
        numero = st.text_input("Número do processo", placeholder="Ex: 2024.001")
        requerente = st.text_input("Requerente", placeholder="Nome da pessoa/empresa")
        rt = st.text_input("RT (Responsável Técnico)", placeholder="Nome do arquiteto/engenheiro")
        analista = st.text_input("Analista", placeholder="Seu nome")
        uso = st.selectbox("Uso do imóvel", ["Residencial", "Comercial", "Industrial", "Misto", "Outro"])
        area = st.number_input("Área total (m²)", min_value=0.0, step=0.1)
        if st.button("Cadastrar Processo", key="btn_cadastrar_processo"):
            if numero and requerente and rt and analista and area > 0:
                cadastrar_processo(numero, requerente, rt, analista, uso, area)
            else:
                st.error("❌ Preencha todos os campos!")
    with col2:
        st.subheader("📋 Processos Cadastrados")
        processos = listar_processos()
        if processos:
            df = pd.DataFrame(processos, columns=["ID", "Número", "Requerente", "RT", "Uso", "Área (m²)", "Status"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nenhum processo cadastrado ainda.")
# ABA 2: LEGISLAÇÕES
with tab2:
    st.header("Gerenciar Legislações")
    col1, col2 = st.columns(2)
  with col1:
    st.subheader("➕ Cadastrar Legislação")
    nome_leg = st.text_input("Nome da legislação", placeholder="Ex: Lei de Uso e Ocupação do Solo")
    desc_leg = st.text_area("Descrição", placeholder="Descrição da legislação")

    # ADICIONE ISSO:
    pdf_file = st.file_uploader("📎 Anexar PDF da Lei", type=['pdf'], key="upload_pdf_leg")

    if st.button("Cadastrar Legislação", key="btn_cadastrar_leg"):
        if nome_leg and desc_leg:
            cadastrar_legislacao(nome_leg, desc_leg, pdf_file)
        else:
            st.error("❌ Preencha todos os campos!")
def obter_pdf_legislacao(legislacao_id):
    cursor.execute('SELECT pdf_nome, pdf_conteudo FROM legislacoes WHERE id = ?', (legislacao_id,))
    resultado = cursor.fetchone()
    return resultado if resultado else (None, None)

    with col2:
    st.subheader("📚 Legislações Cadastradas")
    legislacoes = listar_legislacoes()
    if legislacoes:
        for leg in legislacoes:
            col_a, col_b = st.columns([4, 1])
            col_a.write(f"**ID {leg[0]}** - {leg[1]}")

            # Verificar se tem PDF
            pdf_nome, pdf_conteudo = obter_pdf_legislacao(leg[0])
            if pdf_conteudo:
                col_b.download_button(
                    label="📄 PDF",
                    data=pdf_conteudo,
                    file_name=pdf_nome,
                    mime="application/pdf",
                    key=f"download_pdf_{leg[0]}"
                )
    else:
        st.info("Nenhuma legislação cadastrada ainda.")
    st.divider()
    st.subheader("➕ Adicionar Regra a Legislação")
    legislacoes = listar_legislacoes()
    if legislacoes:
        leg_selecionada = st.selectbox("Selecione a legislação",
                                       options=[f"ID {l[0]} - {l[1]}" for l in legislacoes],
                                       key="select_leg_regra")
        leg_id = int(leg_selecionada.split()[1])
        col1, col2 = st.columns(2)
        with col1:
            artigo = st.text_input("Artigo", placeholder="Ex: Art. 45")
            descricao_regra = st.text_area("Descrição da regra", placeholder="Descrição detalhada")
            campo = st.selectbox("Campo a validar",
                                ["area_total", "uso", "estatus", "numero_processo"])
        with col2:
            operador = st.selectbox("Operador", [">=", "<=", ">", "<", "==", "!="])
            valor_ref = st.number_input("Valor de referência", step=0.1)
            mensagem = st.text_input("Mensagem de erro", placeholder="Mensagem quando violar a regra")
        if st.button("Adicionar Regra", key="btn_adicionar_regra"):
            if artigo and descricao_regra and campo and mensagem:
                adicionar_regra(leg_id, artigo, descricao_regra, campo, operador, valor_ref, mensagem)
            else:
                st.error("❌ Preencha todos os campos!")
    else:
        st.warning("⚠️ Cadastre uma legislação primeiro!")
# ABA 3: VALIDAR
with tab3:
    st.header("Validar Processo contra Legislação")
    processos = listar_processos()
    legislacoes = listar_legislacoes()
    if processos and legislacoes:
        col1, col2 = st.columns(2)
        with col1:
            proc_selecionado = st.selectbox("Selecione o processo",
                                           options=[f"ID {p[0]} - {p[1]}" for p in processos],
                                           key="select_proc_validar")
            proc_id = int(proc_selecionado.split()[1])
        with col2:
            leg_selecionada = st.selectbox("Selecione a legislação",
                                          options=[f"ID {l[0]} - {l[1]}" for l in legislacoes],
                                          key="select_leg_validar")
            leg_id = int(leg_selecionada.split()[1])
        if st.button("🔍 Validar", key="btn_validar"):
            resultado = validar_processo(proc_id, leg_id)
            if resultado:
                st.divider()
                st.subheader(f"📋 Resultado da Validação — Processo {resultado['numero_processo']}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Total de Regras", resultado['total_regras'])
                col2.metric("✅ Conformidades", resultado['total_conformidades'])
                col3.metric("❌ Violações", resultado['total_violacoes'])
                st.divider()
                if resultado['conformidades']:
                    st.subheader("✅ Regras Conformes")
                    for c in resultado['conformidades']:
                        st.success(f"**{c['artigo']}:** {c['descricao']}")
                if resultado['violacoes']:
                    st.subheader("❌ Regras Violadas")
                    for v in resultado['violacoes']:
                        st.error(f"**{v['artigo']}:** {v['descricao']}")
                        st.write(f"📌 {v['mensagem']}")
                        st.write(f"Esperado: `{v['valor_esperado']}` | Encontrado: `{v['valor_encontrado']}`")
    else:
        st.warning("⚠️ Cadastre processos e legislações primeiro!")
# ABA 4: RELATÓRIOS
with tab4:
    st.header("Gerar Relatórios")
    processos = listar_processos()
    legislacoes = listar_legislacoes()
    if processos and legislacoes:
        proc_selecionado = st.selectbox("Selecione o processo",
                                       options=[f"ID {p[0]} - {p[1]}" for p in processos],
                                       key="select_proc_relatorio")
        proc_id = int(proc_selecionado.split()[1])
        leg_selecionada = st.selectbox("Selecione a legislação",
                                      options=[f"ID {l[0]} - {l[1]}" for l in legislacoes],
                                      key="select_leg_relatorio")
        leg_id = int(leg_selecionada.split()[1])
        if st.button("📊 Gerar Relatório Excel", key="btn_relatorio"):
            resultado = validar_processo(proc_id, leg_id)
            if resultado:
                # Criar Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Aba 1: Resumo
                    resumo_data = {
                        'Campo': ['Número do Processo', 'Requerente', 'Total de Regras', 'Conformidades', 'Violações', 'Data'],
                        'Valor': [resultado['numero_processo'], resultado['requerente'],
                                 resultado['total_regras'], resultado['total_conformidades'],
                                 resultado['total_violacoes'], datetime.now().strftime('%d/%m/%Y %H:%M')]
                    }
                    df_resumo = pd.DataFrame(resumo_data)
                    df_resumo.to_excel(writer, sheet_name='Resumo', index=False)
                    # Aba 2: Conformidades
                    if resultado['conformidades']:
                        df_conf = pd.DataFrame(resultado['conformidades'])
                        df_conf.to_excel(writer, sheet_name='Conformidades', index=False)
                    # Aba 3: Violações
                    if resultado['violacoes']:
                        df_viol = pd.DataFrame(resultado['violacoes'])
                        df_viol.to_excel(writer, sheet_name='Violações', index=False)
                output.seek(0)
                st.download_button(
                    label="📥 Baixar Relatório Excel",
                    data=output.getvalue(),
                    file_name=f"relatorio_{resultado['numero_processo']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.success("✅ Relatório gerado com sucesso!")
    else:
        st.warning("⚠️ Cadastre processos e legislações primeiro!")
# Rodapé
st.divider()
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p><strong>🏛️ Sistema de Validação de Processos</strong></p>
    <p>Prefeitura de Contagem — Setor de Liberação de Alvarás</p>
    <p style='font-size: 0.8em; color: gray;'>Desenvolvido com Streamlit</p>
</div>
""", unsafe_allow_html=True)
