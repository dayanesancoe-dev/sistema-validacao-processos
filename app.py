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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs_legislacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            legislacao_id INTEGER NOT NULL,
            pdf_nome TEXT NOT NULL,
            pdf_conteudo BLOB NOT NULL,
            data_upload TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (legislacao_id) REFERENCES legislacoes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs_projeto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            pdf_nome TEXT NOT NULL,
            pdf_conteudo BLOB NOT NULL,
            tipo_documento TEXT,
            data_upload TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )
    ''')

    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# ==================== FUNÇÕES DE PROCESSOS ====================

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

def editar_processo(processo_id, numero, requerente, rt, analista, uso, area, status):
    try:
        cursor.execute('''
            UPDATE processos 
            SET numero_processo = ?, requerente = ?, rt = ?, analista = ?, uso = ?, area_total = ?, estatus = ?
            WHERE id = ?
        ''', (numero, requerente, rt, analista, uso, area, status, processo_id))
        conn.commit()
        st.success(f"✅ Processo {numero} atualizado com sucesso!")
        return True
    except Exception as e:
        st.error(f"❌ Erro ao atualizar: {str(e)}")
        return False

def deletar_processo(processo_id):
    try:
        # Deletar PDFs relacionados primeiro
        cursor.execute('DELETE FROM pdfs_projeto WHERE processo_id = ?', (processo_id,))
        # Deletar o processo
        cursor.execute('DELETE FROM processos WHERE id = ?', (processo_id,))
        conn.commit()
        st.success("✅ Processo deletado com sucesso!")
        return True
    except Exception as e:
        st.error(f"❌ Erro ao deletar: {str(e)}")
        return False

def obter_processo(processo_id):
    cursor.execute('SELECT * FROM processos WHERE id = ?', (processo_id,))
    return cursor.fetchone()

def listar_processos():
    cursor.execute('SELECT id, numero_processo, requerente, rt, uso, area_total, estatus FROM processos')
    return cursor.fetchall()

# ==================== FUNÇÕES DE LEGISLAÇÕES ====================

def cadastrar_legislacao(nome, descricao):
    try:
        cursor.execute('''
            INSERT INTO legislacoes (nome, descricao)
            VALUES (?, ?)
        ''', (nome, descricao))
        conn.commit()
        st.success(f"✅ Legislação '{nome}' cadastrada com sucesso!")
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        st.error(f"❌ Legislação '{nome}' já existe!")
        return None

def editar_legislacao(legislacao_id, nome, descricao):
    try:
        cursor.execute('''
            UPDATE legislacoes 
            SET nome = ?, descricao = ?
            WHERE id = ?
        ''', (nome, descricao, legislacao_id))
        conn.commit()
        st.success(f"✅ Legislação '{nome}' atualizada com sucesso!")
        return True
    except Exception as e:
        st.error(f"❌ Erro ao atualizar: {str(e)}")
        return False

def deletar_legislacao(legislacao_id):
    try:
        # Deletar regras relacionadas
        cursor.execute('DELETE FROM regras_legislacao WHERE legislacao_id = ?', (legislacao_id,))
        # Deletar PDFs relacionados
        cursor.execute('DELETE FROM pdfs_legislacao WHERE legislacao_id = ?', (legislacao_id,))
        # Deletar a legislação
        cursor.execute('DELETE FROM legislacoes WHERE id = ?', (legislacao_id,))
        conn.commit()
        st.success("✅ Legislação deletada com sucesso!")
        return True
    except Exception as e:
        st.error(f"❌ Erro ao deletar: {str(e)}")
        return False

def obter_legislacao(legislacao_id):
    cursor.execute('SELECT * FROM legislacoes WHERE id = ?', (legislacao_id,))
    return cursor.fetchone()

def listar_legislacoes():
    cursor.execute('SELECT id, nome, descricao FROM legislacoes')
    return cursor.fetchall()

# ==================== FUNÇÕES DE PDFs ====================

def anexar_pdf_projeto(processo_id, pdf_file, tipo_doc="Projeto"):
    try:
        pdf_bytes = pdf_file.read()
        pdf_nome = pdf_file.name
        cursor.execute('''
            INSERT INTO pdfs_projeto (processo_id, pdf_nome, pdf_conteudo, tipo_documento)
            VALUES (?, ?, ?, ?)
        ''', (processo_id, pdf_nome, pdf_bytes, tipo_doc))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao anexar PDF: {str(e)}")
        return False

def listar_pdfs_projeto(processo_id):
    cursor.execute('''
        SELECT id, pdf_nome, tipo_documento, data_upload 
        FROM pdfs_projeto 
        WHERE processo_id = ?
        ORDER BY data_upload DESC
    ''', (processo_id,))
    return cursor.fetchall()

def obter_pdf_projeto_por_id(pdf_id):
    cursor.execute('SELECT pdf_nome, pdf_conteudo FROM pdfs_projeto WHERE id = ?', (pdf_id,))
    resultado = cursor.fetchone()
    return resultado if resultado else (None, None)

def deletar_pdf_projeto(pdf_id):
    try:
        cursor.execute('DELETE FROM pdfs_projeto WHERE id = ?', (pdf_id,))
        conn.commit()
        return True
    except:
        return False

def anexar_pdf_legislacao(legislacao_id, pdf_file):
    try:
        pdf_bytes = pdf_file.read()
        pdf_nome = pdf_file.name
        cursor.execute('''
            INSERT INTO pdfs_legislacao (legislacao_id, pdf_nome, pdf_conteudo)
            VALUES (?, ?, ?)
        ''', (legislacao_id, pdf_nome, pdf_bytes))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erro ao anexar PDF: {str(e)}")
        return False

def listar_pdfs_legislacao(legislacao_id):
    cursor.execute('''
        SELECT id, pdf_nome, data_upload 
        FROM pdfs_legislacao 
        WHERE legislacao_id = ?
        ORDER BY data_upload DESC
    ''', (legislacao_id,))
    return cursor.fetchall()

def obter_pdf_legislacao_por_id(pdf_id):
    cursor.execute('SELECT pdf_nome, pdf_conteudo FROM pdfs_legislacao WHERE id = ?', (pdf_id,))
    resultado = cursor.fetchone()
    return resultado if resultado else (None, None)

def deletar_pdf_legislacao(pdf_id):
    try:
        cursor.execute('DELETE FROM pdfs_legislacao WHERE id = ?', (pdf_id,))
        conn.commit()
        return True
    except:
        return False

# ==================== FUNÇÕES DE REGRAS ====================

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
        SELECT id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro
        FROM regras_legislacao
        WHERE legislacao_id = ?
    ''', (legislacao_id,))
    return cursor.fetchall()

def deletar_regra(regra_id):
    try:
        cursor.execute('DELETE FROM regras_legislacao WHERE id = ?', (regra_id,))
        conn.commit()
        return True
    except:
        return False

# ==================== FUNÇÃO DE VALIDAÇÃO ====================

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

        resultado = False
        try:
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
        except:
            pass

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

# ==================== INTERFACE PRINCIPAL ====================

tab1, tab2, tab3, tab4 = st.tabs(["📝 Processos", "📚 Legislações", "✅ Validar", "📊 Relatórios"])

# ==================== ABA 1: PROCESSOS ====================
with tab1:
    st.header("Gerenciar Processos")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Cadastrar Novo Processo")
        numero = st.text_input("Número do processo", placeholder="Ex: 2024.001", key="novo_numero")
        requerente = st.text_input("Requerente", placeholder="Nome da pessoa/empresa", key="novo_requerente")
        rt = st.text_input("RT (Responsável Técnico)", placeholder="Nome do arquiteto/engenheiro", key="novo_rt")
        analista = st.text_input("Analista", placeholder="Seu nome", key="novo_analista")
        uso = st.selectbox("Uso do imóvel", ["Residencial", "Comercial", "Industrial", "Misto", "Outro"], key="novo_uso")
        area = st.number_input("Área total (m²)", min_value=0.0, step=0.1, key="nova_area")

        if st.button("Cadastrar Processo", key="btn_cadastrar_processo"):
            if numero and requerente and rt and analista and area > 0:
                if cadastrar_processo(numero, requerente, rt, analista, uso, area):
                    st.rerun()
            else:
                st.error("❌ Preencha todos os campos!")

    with col2:
        st.subheader("📋 Processos Cadastrados")
        processos = listar_processos()
        if processos:
            for proc in processos:
                with st.expander(f"**{proc[1]}** - {proc[2]}"):
                    col_info, col_acoes = st.columns([3, 1])

                    with col_info:
                        st.write(f"**ID:** {proc[0]}")
                        st.write(f"**Número:** {proc[1]}")
                        st.write(f"**Requerente:** {proc[2]}")
                        st.write(f"**RT:** {proc[3]}")
                        st.write(f"**Uso:** {proc[4]}")
                        st.write(f"**Área:** {proc[5]} m²")
                        st.write(f"**Status:** {proc[6]}")

                    with col_acoes:
                        # Botão Editar
                        if st.button("✏️ Editar", key=f"btn_edit_proc_{proc[0]}"):
                            st.session_state[f'editando_proc_{proc[0]}'] = True
                            st.rerun()

                        # Botão Deletar
                        if st.button("🗑️ Deletar", key=f"btn_del_proc_{proc[0]}"):
                            if deletar_processo(proc[0]):
                                st.rerun()

                    # Formulário de edição
                    if st.session_state.get(f'editando_proc_{proc[0]}', False):
                        st.divider()
                        st.write("**Editar Processo:**")
                        processo_dados = obter_processo(proc[0])

                        edit_numero = st.text_input("Número", value=processo_dados[1], key=f"edit_num_{proc[0]}")
                        edit_requerente = st.text_input("Requerente", value=processo_dados[2], key=f"edit_req_{proc[0]}")
                        edit_rt = st.text_input("RT", value=processo_dados[3], key=f"edit_rt_{proc[0]}")
                        edit_analista = st.text_input("Analista", value=processo_dados[4], key=f"edit_ana_{proc[0]}")
                        edit_uso = st.selectbox("Uso", ["Residencial", "Comercial", "Industrial", "Misto", "Outro"], 
                                               index=["Residencial", "Comercial", "Industrial", "Misto", "Outro"].index(processo_dados[5]), 
                                               key=f"edit_uso_{proc[0]}")
                        edit_area = st.number_input("Área (m²)", value=float(processo_dados[6]), step=0.1, key=f"edit_area_{proc[0]}")
                        edit_status = st.selectbox("Status", ["Em análise", "Aprovado", "Reprovado", "Pendente"], 
                                                  index=["Em análise", "Aprovado", "Reprovado", "Pendente"].index(processo_dados[7]) if processo_dados[7] in ["Em análise", "Aprovado", "Reprovado", "Pendente"] else 0,
                                                  key=f"edit_status_{proc[0]}")

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("💾 Salvar", key=f"btn_save_proc_{proc[0]}"):
                                if editar_processo(proc[0], edit_numero, edit_requerente, edit_rt, edit_analista, edit_uso, edit_area, edit_status):
                                    st.session_state[f'editando_proc_{proc[0]}'] = False
                                    st.rerun()

                        with col_cancel:
                            if st.button("❌ Cancelar", key=f"btn_cancel_proc_{proc[0]}"):
                                st.session_state[f'editando_proc_{proc[0]}'] = False
                                st.rerun()
        else:
            st.info("Nenhum processo cadastrado ainda.")

# ==================== ABA 2: LEGISLAÇÕES ====================
with tab2:
    st.header("Gerenciar Legislações")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Cadastrar Legislação")
        nome_leg = st.text_input("Nome da legislação", placeholder="Ex: Lei de Uso e Ocupação do Solo", key="nova_leg_nome")
        desc_leg = st.text_area("Descrição", placeholder="Descrição da legislação", key="nova_leg_desc")
        pdfs_leg = st.file_uploader("📎 Anexar PDFs da Lei (múltiplos)", type=['pdf'], accept_multiple_files=True, key="upload_pdfs_leg")

        if st.button("Cadastrar Legislação", key="btn_cadastrar_leg"):
            if nome_leg and desc_leg:
                leg_id = cadastrar_legislacao(nome_leg, desc_leg)
                if leg_id and pdfs_leg:
                    for pdf in pdfs_leg:
                        anexar_pdf_legislacao(leg_id, pdf)
                    st.success(f"✅ {len(pdfs_leg)} PDF(s) anexado(s)!")
                    st.rerun()
            else:
                st.error("❌ Preencha todos os campos!")

    with col2:
        st.subheader("📚 Legislações Cadastradas")
        legislacoes = listar_legislacoes()
        if legislacoes:
            for leg in legislacoes:
                with st.expander(f"**ID {leg[0]}** - {leg[1]}"):
                    col_info, col_acoes = st.columns([3, 1])

                    with col_info:
                        st.write(f"**Descrição:** {leg[2]}")

                        # Mostrar regras
                        regras = listar_regras_legislacao(leg[0])
                        if regras:
                            st.write(f"**Regras cadastradas:** {len(regras)}")

                        # Listar PDFs
                        pdfs = listar_pdfs_legislacao(leg[0])
                        if pdfs:
                            st.write("**PDFs anexados:**")
                            for pdf in pdfs:
                                col_pdf, col_btn = st.columns([3, 1])
                                col_pdf.write(f"📄 {pdf[1]}")

                                pdf_nome, pdf_conteudo = obter_pdf_legislacao_por_id(pdf[0])
                                if pdf_conteudo:
                                    col_btn.download_button(
                                        label="⬇️",
                                        data=pdf_conteudo,
                                        file_name=pdf_nome,
                                        mime="application/pdf",
                                        key=f"download_leg_pdf_{pdf[0]}"
                                    )

                    with col_acoes:
                        # Botão Editar
                        if st.button("✏️ Editar", key=f"btn_edit_leg_{leg[0]}"):
                            st.session_state[f'editando_leg_{leg[0]}'] = True
                            st.rerun()

                        # Botão Deletar
                        if st.button("🗑️ Deletar", key=f"btn_del_leg_{leg[0]}"):
                            if deletar_legislacao(leg[0]):
                                st.rerun()

                    # Formulário de edição
                    if st.session_state.get(f'editando_leg_{leg[0]}', False):
                        st.divider()
                        st.write("**Editar Legislação:**")
                        leg_dados = obter_legislacao(leg[0])

                        edit_nome = st.text_input("Nome", value=leg_dados[1], key=f"edit_leg_nome_{leg[0]}")
                        edit_desc = st.text_area("Descrição", value=leg_dados[2], key=f"edit_leg_desc_{leg[0]}")

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("💾 Salvar", key=f"btn_save_leg_{leg[0]}"):
                                if editar_legislacao(leg[0], edit_nome, edit_desc):
                                    st.session_state[f'editando_leg_{leg[0]}'] = False
                                    st.rerun()

                        with col_cancel:
                            if st.button("❌ Cancelar", key=f"btn_cancel_leg_{leg[0]}"):
                                st.session_state[f'editando_leg_{leg[0]}'] = False
                                st.rerun()
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

        # Mostrar regras existentes
        regras_existentes = listar_regras_legislacao(leg_id)
        if regras_existentes:
            st.write("**Regras cadastradas:**")
            for regra in regras_existentes:
                col_regra, col_del = st.columns([5, 1])
                col_regra.write(f"📌 **{regra[1]}:** {regra[2]} | Campo: `{regra[3]}` | Condição: `{regra[4]} {regra[5]}`")
                if col_del.button("🗑️", key=f"del_regra_{regra[0]}"):
                    if deletar_regra(regra[0]):
                        st.success("Regra deletada!")
                        st.rerun()

        st.divider()
        st.write("**Adicionar nova regra:**")

        col1, col2 = st.columns(2)

        with col1:
            artigo = st.text_input("Artigo", placeholder="Ex: Art. 45", key="novo_artigo")
            descricao_regra = st.text_area("Descrição da regra", placeholder="Descrição detalhada", key="nova_desc_regra")
            campo = st.selectbox("Campo a validar",
                               ["area_total", "uso", "estatus", "numero_processo"], key="novo_campo")

        with col2:
            operador = st.selectbox("Operador", [">=", "<=", ">", "<", "==", "!="], key="novo_operador")
            valor_ref = st.number_input("Valor de referência", step=0.1, key="novo_valor")
            mensagem = st.text_input("Mensagem de erro", placeholder="Mensagem quando violar a regra", key="nova_mensagem")

        if st.button("Adicionar Regra", key="btn_adicionar_regra"):
            if artigo and descricao_regra and campo and mensagem:
                if adicionar_regra(leg_id, artigo, descricao_regra, campo, operador, valor_ref, mensagem):
                    st.rerun()
            else:
                st.error("❌ Preencha todos os campos!")
    else:
        st.warning("⚠️ Cadastre uma legislação primeiro!")

# ==================== ABA 3: VALIDAR ====================
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

        st.divider()

        st.subheader("📎 Gerenciar PDFs do Projeto")

        pdfs_anexados = listar_pdfs_projeto(proc_id)
        if pdfs_anexados:
            st.write("**PDFs anexados ao processo:**")
            for pdf in pdfs_anexados:
                col_a, col_b, col_c, col_d = st.columns([2, 2, 1, 1])
                col_a.write(f"📄 {pdf[1]}")
                col_b.write(f"*{pdf[2]}*")

                pdf_nome, pdf_conteudo = obter_pdf_projeto_por_id(pdf[0])
                if pdf_conteudo:
                    col_c.download_button(
                        label="⬇️",
                        data=pdf_conteudo,
                        file_name=pdf_nome,
                        mime="application/pdf",
                        key=f"download_proj_pdf_{pdf[0]}"
                    )

                    if col_d.button("🗑️", key=f"del_proj_pdf_{pdf[0]}"):
                        if deletar_pdf_projeto(pdf[0]):
                            st.success("PDF deletado!")
                            st.rerun()

        st.write("**Adicionar novos PDFs:**")
        novos_pdfs_projeto = st.file_uploader(
            "Selecione os PDFs do projeto", 
            type=['pdf'], 
            accept_multiple_files=True,
            key="upload_pdfs_projeto"
        )

        tipo_doc = st.selectbox("Tipo de documento", 
                                ["Planta Baixa", "Corte", "Fachada", "Situação", "Locação", "Outro"],
                                key="tipo_doc_projeto")

        if novos_pdfs_projeto:
            if st.button("💾 Salvar PDFs do Projeto", key="btn_salvar_pdfs_projeto"):
                sucesso = 0
                for pdf in novos_pdfs_projeto:
                    if anexar_pdf_projeto(proc_id, pdf, tipo_doc):
                        sucesso += 1

                if sucesso > 0:
                    st.success(f"✅ {sucesso} PDF(s) anexado(s) com sucesso!")
                    st.rerun()

        st.divider()

        if st.button("🔍 Validar Processo e Gerar Relatório", key="btn_validar"):
            resultado = validar_processo(proc_id, leg_id)

            if resultado:
                st.divider()
                st.subheader(f"📋 Resultado da Validação — Processo {resultado['numero_processo']}")

                col1, col2, col3 = st.columns(3)
                col1.metric("Total de Regras", resultado['total_regras'])
                col2.metric("✅ Conformidades", resultado['total_conformidades'])
                col3.metric("❌ Violações", resultado['total_violacoes'])

                if resultado['total_violacoes'] == 0:
                    st.success("🎉 **PROJETO APROVADO** - Todas as regras foram atendidas!")
                else:
                    st.error(f"⚠️ **PROJETO REPROVADO** - {resultado['total_violacoes']} violação(ões) encontrada(s)")

                st.divider()

                if resultado['conformidades']:
                    with st.expander("✅ Regras Conformes", expanded=True):
                        for c in resultado['conformidades']:
                            st.success(f"**{c['artigo']}:** {c['descricao']}")

                if resultado['violacoes']:
                    with st.expander("❌ Regras Violadas", expanded=True):
                        for v in resultado['violacoes']:
                            st.error(f"**{v['artigo']}:** {v['descricao']}")
                            st.write(f"📌 {v['mensagem']}")
                            st.write(f"**Esperado:** `{v['valor_esperado']}` | **Encontrado:** `{v['valor_encontrado']}`")
    else:
        st.warning("⚠️ Cadastre processos e legislações primeiro!")

# ==================== ABA 4: RELATÓRIOS ====================
with tab4:
    st.header("Gerar Relatórios de Validação")

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
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    status = "APROVADO" if resultado['total_violacoes'] == 0 else "REPROVADO"
                    resumo_data = {
                        'Campo': ['Número do Processo', 'Requerente', 'Status', 'Total de Regras', 'Conformidades', 'Violações', 'Data do Relatório'],
                        'Valor': [resultado['numero_processo'], resultado['requerente'], status,
                                  resultado['total_regras'], resultado['total_conformidades'],
                                  resultado['total_violacoes'], datetime.now().strftime('%d/%m/%Y %H:%M')]
                    }
                    df_resumo = pd.DataFrame(resumo_data)
                    df_resumo.to_excel(writer, sheet_name='Resumo', index=False)

                    if resultado['conformidades']:
                        df_conf = pd.DataFrame(resultado['conformidades'])
                        df_conf.to_excel(writer, sheet_name='Conformidades', index=False)

                    if resultado['violacoes']:
                        df_viol = pd.DataFrame(resultado['violacoes'])
                        df_viol.to_excel(writer, sheet_name='Violações', index=False)

                output.seek(0)

                st.download_button(
                    label="📥 Baixar Relatório Excel Completo",
                    data=output.getvalue(),
                    file_name=f"relatorio_validacao_{resultado['numero_processo']}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
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
