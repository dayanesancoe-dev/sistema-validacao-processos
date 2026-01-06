import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io
import re

# Tentar importar PyPDF2 e reportlab
try:
    import PyPDF2
    PDF_DISPONIVEL = True
except ImportError:
    PDF_DISPONIVEL = False
    st.warning("⚠️ PyPDF2 não instalado. Instale com: pip install PyPDF2")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False
    st.warning("⚠️ ReportLab não instalado. Instale com: pip install reportlab")

# Configuração da página
st.set_page_config(
    page_title="Sistema de Validação de Processos",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem** — Liberação de Alvarás de Construção")

# Inicializar banco de dados
@st.cache_resource
def init_db():
    conn = sqlite3.connect('processos.db', check_same_thread=False)
    cursor = conn.cursor()

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

# ==================== FUNÇÕES AUXILIARES ====================

def extrair_texto_pdf(pdf_bytes):
    if not PDF_DISPONIVEL:
        return "[PyPDF2 não instalado]"

    try:
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        texto = ""
        for page in pdf_reader.pages:
            texto += page.extract_text() + "\n"
        return texto
    except Exception as e:
        return f"[Erro ao extrair texto: {str(e)}]"

def analisar_texto_projeto(texto_projeto, regras):
    analises = []

    for regra in regras:
        artigo = regra[1]
        descricao = regra[2]

        palavras_chave = extrair_palavras_chave(descricao)
        encontradas = []

        for palavra in palavras_chave:
            if palavra.lower() in texto_projeto.lower():
                encontradas.append(palavra)

        if encontradas:
            analises.append({
                'artigo': artigo,
                'descricao': descricao,
                'palavras_encontradas': encontradas,
                'status': 'encontrado'
            })
        else:
            analises.append({
                'artigo': artigo,
                'descricao': descricao,
                'palavras_encontradas': [],
                'status': 'nao_encontrado'
            })

    return analises

def extrair_palavras_chave(texto):
    stopwords = ['de', 'da', 'do', 'a', 'o', 'e', 'para', 'com', 'em', 'ser', 'deve', 'que', 'ter']
    palavras = re.findall(r'\b\w{4,}\b', texto.lower())
    return [p for p in palavras if p not in stopwords][:5]

def gerar_relatorio_pdf(resultado, analise_textual):
    if not REPORTLAB_DISPONIVEL:
        st.error("ReportLab não está instalado. Instale com: pip install reportlab")
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    subtitulo_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2d5aa6'),
        spaceAfter=12
    )

    story.append(Paragraph("RELATÓRIO DE ANÁLISE DE CONFORMIDADE", titulo_style))
    story.append(Paragraph("Prefeitura de Contagem - Setor de Liberação de Alvarás", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("DADOS DO PROCESSO", subtitulo_style))

    dados_processo = [
        ['Número do Processo:', resultado['numero_processo']],
        ['Requerente:', resultado['requerente']],
        ['Data do Relatório:', datetime.now().strftime('%d/%m/%Y às %H:%M')],
        ['Status:', 'APROVADO' if resultado['total_violacoes'] == 0 else 'REPROVADO']
    ]

    tabela_processo = Table(dados_processo, colWidths=[5*cm, 10*cm])
    tabela_processo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0fe')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(tabela_processo)
    story.append(Spacer(1, 0.8*cm))

    story.append(Paragraph("RESUMO DA VALIDAÇÃO", subtitulo_style))

    resumo_dados = [
        ['Total de Regras', str(resultado['total_regras'])],
        ['Conformidades', str(resultado['total_conformidades'])],
        ['Violações', str(resultado['total_violacoes'])]
    ]

    tabela_resumo = Table(resumo_dados, colWidths=[8*cm, 7*cm])
    tabela_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#34a853') if resultado['total_violacoes'] == 0 else colors.HexColor('#ea4335')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
    ]))
    story.append(tabela_resumo)
    story.append(Spacer(1, 1*cm))

    if resultado['violacoes']:
        story.append(PageBreak())
        story.append(Paragraph("PONTOS QUE DEVEM SER CORRIGIDOS", subtitulo_style))
        story.append(Spacer(1, 0.3*cm))

        for i, v in enumerate(resultado['violacoes'], 1):
            violacao_texto = f"<b>Violação {i}: {v['artigo']}</b><br/><b>Descrição:</b> {v['descricao']}<br/><b>Problema:</b> {v['mensagem']}<br/><b>Esperado:</b> {v['valor_esperado']}<br/><b>Encontrado:</b> {v['valor_encontrado']}"
            story.append(Paragraph(violacao_texto, styles['Normal']))
            story.append(Spacer(1, 0.5*cm))

    if resultado['conformidades']:
        story.append(PageBreak())
        story.append(Paragraph("REGRAS CONFORMES", subtitulo_style))
        for c in resultado['conformidades']:
            story.append(Paragraph(f"<b>{c['artigo']}:</b> {c['descricao']}", styles['Normal']))
            story.append(Spacer(1, 0.2*cm))

    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("_" * 80, styles['Normal']))
    story.append(Paragraph(f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ==================== FUNÇÕES DO BANCO ====================

def cadastrar_processo(numero, requerente, rt, analista, uso, area):
    try:
        cursor.execute('''
            INSERT INTO processos (numero_processo, requerente, rt, analista, uso, area_total)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (numero, requerente, rt, analista, uso, area))
        conn.commit()
        st.success(f"✅ Processo {numero} cadastrado!")
        return True
    except sqlite3.IntegrityError:
        st.error(f"❌ Processo {numero} já existe!")
        return False

def deletar_processo(processo_id):
    try:
        cursor.execute('DELETE FROM pdfs_projeto WHERE processo_id = ?', (processo_id,))
        cursor.execute('DELETE FROM processos WHERE id = ?', (processo_id,))
        conn.commit()
        st.success("✅ Processo deletado!")
        return True
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        return False

def listar_processos():
    cursor.execute('SELECT id, numero_processo, requerente, rt, uso, area_total, estatus FROM processos')
    return cursor.fetchall()

def cadastrar_legislacao(nome, descricao):
    try:
        cursor.execute('INSERT INTO legislacoes (nome, descricao) VALUES (?, ?)', (nome, descricao))
        conn.commit()
        st.success(f"✅ Legislação '{nome}' cadastrada!")
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        st.error(f"❌ Legislação '{nome}' já existe!")
        return None

def deletar_legislacao(legislacao_id):
    try:
        cursor.execute('DELETE FROM regras_legislacao WHERE legislacao_id = ?', (legislacao_id,))
        cursor.execute('DELETE FROM pdfs_legislacao WHERE legislacao_id = ?', (legislacao_id,))
        cursor.execute('DELETE FROM legislacoes WHERE id = ?', (legislacao_id,))
        conn.commit()
        st.success("✅ Legislação deletada!")
        return True
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        return False

def listar_legislacoes():
    cursor.execute('SELECT id, nome, descricao FROM legislacoes')
    return cursor.fetchall()

def anexar_pdf_projeto(processo_id, pdf_file, tipo_doc="Projeto"):
    try:
        pdf_bytes = pdf_file.read()
        cursor.execute('INSERT INTO pdfs_projeto (processo_id, pdf_nome, pdf_conteudo, tipo_documento) VALUES (?, ?, ?, ?)', 
                      (processo_id, pdf_file.name, pdf_bytes, tipo_doc))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        return False

def listar_pdfs_projeto(processo_id):
    cursor.execute('SELECT id, pdf_nome, tipo_documento, data_upload FROM pdfs_projeto WHERE processo_id = ? ORDER BY data_upload DESC', (processo_id,))
    return cursor.fetchall()

def obter_pdf_projeto_por_id(pdf_id):
    cursor.execute('SELECT pdf_nome, pdf_conteudo FROM pdfs_projeto WHERE id = ?', (pdf_id,))
    resultado = cursor.fetchone()
    return resultado if resultado else (None, None)

def obter_todos_pdfs_projeto(processo_id):
    cursor.execute('SELECT pdf_conteudo FROM pdfs_projeto WHERE processo_id = ?', (processo_id,))
    return cursor.fetchall()

def deletar_pdf_projeto(pdf_id):
    try:
        cursor.execute('DELETE FROM pdfs_projeto WHERE id = ?', (pdf_id,))
        conn.commit()
        return True
    except:
        return False

def adicionar_regra(leg_id, artigo, descricao, campo, operador, valor, mensagem):
    try:
        cursor.execute('''
            INSERT INTO regras_legislacao (legislacao_id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (leg_id, artigo, descricao, campo, operador, valor, mensagem))
        conn.commit()
        st.success(f"✅ Regra '{artigo}' adicionada!")
        return True
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        return False

def listar_regras_legislacao(legislacao_id):
    cursor.execute('SELECT id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro FROM regras_legislacao WHERE legislacao_id = ?', (legislacao_id,))
    return cursor.fetchall()

def deletar_regra(regra_id):
    try:
        cursor.execute('DELETE FROM regras_legislacao WHERE id = ?', (regra_id,))
        conn.commit()
        return True
    except:
        return False

def validar_processo(processo_id, legislacao_id):
    cursor.execute('SELECT * FROM processos WHERE id = ?', (processo_id,))
    processo = cursor.fetchone()

    if not processo:
        return None

    cursor.execute('SELECT id, artigo, descricao, campo_validacao, operador, valor_referencia, mensagem_erro FROM regras_legislacao WHERE legislacao_id = ?', (legislacao_id,))
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
            conformidades.append({'artigo': regra[1], 'descricao': regra[2], 'id': regra[0]})
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

    pdfs_projeto = obter_todos_pdfs_projeto(processo_id)
    texto_projeto_completo = ""
    for pdf_bytes in pdfs_projeto:
        if pdf_bytes and pdf_bytes[0]:
            texto_projeto_completo += extrair_texto_pdf(pdf_bytes[0]) + "\n\n"

    analise_textual = analisar_texto_projeto(texto_projeto_completo, regras) if texto_projeto_completo else []

    return {
        'numero_processo': processo[1],
        'requerente': processo[2],
        'total_regras': len(regras),
        'total_conformidades': len(conformidades),
        'total_violacoes': len(violacoes),
        'conformidades': conformidades,
        'violacoes': violacoes,
        'analise_textual': analise_textual
    }

# ==================== INTERFACE ====================

tab1, tab2, tab3, tab4 = st.tabs(["📝 Processos", "📚 Legislações", "✅ Validar", "📊 Relatórios"])

# ABA 1: PROCESSOS
with tab1:
    st.header("Gerenciar Processos")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Cadastrar Processo")
        numero = st.text_input("Número", key="proc_numero_input")
        requerente = st.text_input("Requerente", key="proc_req_input")
        rt = st.text_input("RT", key="proc_rt_input")
        analista = st.text_input("Analista", key="proc_ana_input")
        uso = st.selectbox("Uso", ["Residencial", "Comercial", "Industrial", "Misto", "Outro"], key="proc_uso_select")
        area = st.number_input("Área (m²)", min_value=0.0, step=0.1, key="proc_area_input")

        if st.button("Cadastrar", key="proc_cad_btn"):
            if numero and requerente and rt and analista and area > 0:
                cadastrar_processo(numero, requerente, rt, analista, uso, area)
                st.rerun()

    with col2:
        st.subheader("📋 Processos")
        processos = listar_processos()
        if processos:
            for proc in processos:
                with st.expander(f"{proc[1]} - {proc[2]}", expanded=False):
                    st.write(f"RT: {proc[3]} | Uso: {proc[4]} | Área: {proc[5]} m²")
                    if st.button("🗑️ Deletar", key=f"proc_del_btn_{proc[0]}"):
                        deletar_processo(proc[0])
                        st.rerun()

# ABA 2: LEGISLAÇÕES
with tab2:
    st.header("Gerenciar Legislações")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Cadastrar Legislação")
        nome_leg = st.text_input("Nome", key="leg_nome_input")
        desc_leg = st.text_area("Descrição", key="leg_desc_input")

        if st.button("Cadastrar", key="leg_cad_btn"):
            if nome_leg and desc_leg:
                cadastrar_legislacao(nome_leg, desc_leg)
                st.rerun()

    with col2:
        st.subheader("📚 Legislações")
        legislacoes = listar_legislacoes()
        if legislacoes:
            for leg in legislacoes:
                with st.expander(leg[1], expanded=False):
                    st.write(leg[2])
                    if st.button("🗑️ Deletar", key=f"leg_del_btn_{leg[0]}"):
                        deletar_legislacao(leg[0])
                        st.rerun()

    st.divider()
    st.subheader("➕ Adicionar Regras")

    if legislacoes:
        leg_sel = st.selectbox("Legislação", [f"ID {l[0]} - {l[1]}" for l in legislacoes], key="regra_leg_select")
        leg_id = int(leg_sel.split()[1])

        regras = listar_regras_legislacao(leg_id)
        if regras:
            st.write("**Regras:**")
            for r in regras:
                col_r, col_d = st.columns([5, 1])
                col_r.write(f"📌 {r[1]}: {r[2]}")
                if col_d.button("🗑️", key=f"regra_del_btn_{r[0]}"):
                    deletar_regra(r[0])
                    st.rerun()

        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            artigo = st.text_input("Artigo", key="regra_art_input")
            descricao = st.text_area("Descrição", key="regra_desc_input")
            campo = st.selectbox("Campo", ["area_total", "uso", "estatus", "numero_processo"], key="regra_campo_select")

        with col2:
            operador = st.selectbox("Operador", [">=", "<=", ">", "<", "==", "!="], key="regra_op_select")
            valor = st.number_input("Valor", step=0.1, key="regra_val_input")
            mensagem = st.text_input("Mensagem", key="regra_msg_input")

        if st.button("Adicionar Regra", key="regra_add_btn"):
            if artigo and descricao and mensagem:
                adicionar_regra(leg_id, artigo, descricao, campo, operador, valor, mensagem)
                st.rerun()

# ABA 3: VALIDAR
with tab3:
    st.header("Validar e Gerar Relatório")

    processos = listar_processos()
    legislacoes = listar_legislacoes()

    if processos and legislacoes:
        col1, col2 = st.columns(2)

        with col1:
            proc_sel = st.selectbox("Processo", [f"ID {p[0]} - {p[1]}" for p in processos], key="val_proc_select")
            proc_id = int(proc_sel.split()[1])

        with col2:
            leg_sel = st.selectbox("Legislação", [f"ID {l[0]} - {l[1]}" for l in legislacoes], key="val_leg_select")
            leg_id = int(leg_sel.split()[1])

        st.divider()
        st.subheader("📎 PDFs do Projeto")

        pdfs = listar_pdfs_projeto(proc_id)
        if pdfs:
            for idx, pdf in enumerate(pdfs):
                col_a, col_b, col_c = st.columns([3, 1, 1])
                col_a.write(f"📄 {pdf[1]}")

                pdf_nome, pdf_cont = obter_pdf_projeto_por_id(pdf[0])
                if pdf_cont:
                    col_b.download_button("⬇️", pdf_cont, pdf_nome, mime="application/pdf", key=f"val_pdf_dl_{pdf[0]}_{idx}")
                    if col_c.button("🗑️", key=f"val_pdf_del_{pdf[0]}_{idx}"):
                        deletar_pdf_projeto(pdf[0])
                        st.rerun()

        novos = st.file_uploader("Anexar PDFs", type=['pdf'], accept_multiple_files=True, key="val_pdf_upload")
        tipo = st.selectbox("Tipo", ["Planta Baixa", "Corte", "Fachada", "Situação"], key="val_tipo_select")

        if novos and st.button("💾 Salvar", key="val_pdf_save_btn"):
            for pdf in novos:
                anexar_pdf_projeto(proc_id, pdf, tipo)
            st.success(f"✅ {len(novos)} PDF(s) anexado(s)!")
            st.rerun()

        st.divider()

        if st.button("🔍 VALIDAR", key="val_validar_btn", type="primary"):
            with st.spinner("Analisando..."):
                resultado = validar_processo(proc_id, leg_id)

            if resultado:
                st.divider()
                st.subheader(f"Resultado - {resultado['numero_processo']}")

                col1, col2, col3 = st.columns(3)
                col1.metric("Regras", resultado['total_regras'])
                col2.metric("✅", resultado['total_conformidades'])
                col3.metric("❌", resultado['total_violacoes'])

                if resultado['total_violacoes'] == 0:
                    st.success("🎉 APROVADO")
                else:
                    st.error(f"⚠️ REPROVADO - {resultado['total_violacoes']} violação(ões)")

                st.divider()

                pdf_rel = gerar_relatorio_pdf(resultado, resultado['analise_textual'])
                if pdf_rel:
                    st.download_button(
                        "📥 BAIXAR RELATÓRIO PDF",
                        pdf_rel,
                        f"relatorio_{resultado['numero_processo']}.pdf",
                        "application/pdf",
                        type="primary",
                        key="val_rel_download_btn"
                    )

                if resultado['violacoes']:
                    with st.expander("❌ Violações", expanded=True):
                        for v in resultado['violacoes']:
                            st.error(f"**{v['artigo']}:** {v['descricao']}")
                            st.write(f"📌 {v['mensagem']}")
                            st.write(f"Esperado: `{v['valor_esperado']}` | Encontrado: `{v['valor_encontrado']}`")
    else:
        st.warning("⚠️ Cadastre processos e legislações primeiro!")

# ABA 4: RELATÓRIOS
with tab4:
    st.header("Histórico")
    st.info("Os relatórios são gerados na aba 'Validar'")

st.divider()
st.markdown("---")
st.markdown("<div style='text-align: center'><p><strong>🏛️ Sistema de Validação de Processos</strong></p><p>Prefeitura de Contagem</p></div>", unsafe_allow_html=True)
