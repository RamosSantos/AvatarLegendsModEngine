"""Small UI translation layer. English is the default; Portuguese keeps source text."""
from __future__ import annotations

import re

LANGUAGE = "en"

# The source GUI was authored in Portuguese. Exact labels/messages are translated
# here so feature code stays independent from the selected UI language.
EN = {
    "Idioma:": "Language:", "Inglês": "English",
    "Pasta do jogo:": "Game folder:", "Selecionar…": "Browse...", "Selecionar�": "Browse...", "Procurar .pak": "Scan for .pak",
    "Pacote:": "Package:", "Filtro de caminho:": "Path filter:", "Nenhum pacote carregado": "No package loaded",
    "Arquivo dentro do pacote": "Path inside package", "Tamanho (bytes)": "Size (bytes)", "Offset": "Offset",
    "Extrair pacote…": "Extract package...", "Extrair pacote�": "Extract package...",
    "Substituir arquivo selecionado…": "Replace selected file...", "Substituir arquivo selecionado�": "Replace selected file...",
    "Configurar ferramentas MUNGED…": "Configure MUNGED tools...", "Configurar ferramentas MUNGED�": "Configure MUNGED tools...", "Visualizar frame MUNGED": "Preview MUNGED frame",
    "Navega��o anima��es…": "Browse animations...", "Navegar animações…": "Browse animations...",
    "Aplicar MUNGED editado…": "Apply edited MUNGED...", "Aplicar MUNGED editado�": "Apply edited MUNGED...", "Abrir pasta de trabalho": "Open workspace folder",
    "Validar área de trabalho": "Validate workspace", "Validar �rea de trabalho": "Validate workspace",
    "Reconstruir pacote modificado…": "Rebuild modified package...", "Reconstruir pacote modificado�": "Rebuild modified package...",
    "Criar perfil de mod...": "Create mod profile...", "Revisar/Reaplicar perfil...": "Review/Reapply profile...",
    "Para frames .munged, configure a pasta do projeto avatar-legends-tools. A GUI extrai para uma área de trabalho, abre a prévia PNG e reconstrói um .pak novo; ela nunca altera o pacote instalado.":
        "For .munged frames, configure the avatar-legends-tools project folder. The GUI extracts to a workspace, opens a PNG preview, and rebuilds a new .pak; it never changes the installed package.",
    "Para frames .munged, configure a pasta do projeto avatar-legends-tools. A GUI extrai para uma �rea de trabalho, ":
        "For .munged frames, configure the avatar-legends-tools project folder. The GUI extracts to a workspace, ",
    "Personagem:": "Character:", "Movimento:": "Motion:",
    "Frames em ordem natural (Ctrl/Shift para selecionar)": "Frames in natural order (Ctrl/Shift to select)",
    "Frame": "Frame", "Estado": "Status", "Modificado": "Modified", "FPS:": "FPS:",
    "Aplicar substitutos selecionados…": "Apply selected replacements...", "Aplicar substitutos selecionadosâ€¦": "Apply selected replacements...", "Aplicar substitutos selecionados�": "Apply selected replacements...",
    "▶ Reproduzir": "▶ Play", "❚❚ Pausar": "❚❚ Pause", "â–¶ Reproduzir": "▶ Play", "âšâš Pausar": "❚❚ Pause",
    "Selecione frames": "Select frames", "Selecione um ou mais frames na lista.": "Select one or more frames from the list.",
    "Pasta com os arquivos .munged substitutos": "Folder containing replacement .munged files",
    "Nenhum pacote": "No package", "Carregue um pacote primeiro.": "Load a package first.",
    "Criar perfil de mod": "Create mod profile", "Perfil criado": "Profile created",
    "Revisar perfil": "Review profile", "Revisar perfil —": "Review profile -",
    "Fechar": "Close", "Reaplicar no workspace...": "Reapply to workspace...",
    "Caminho no pacote": "Package path", "Comparação": "Comparison", "Hash base do perfil": "Profile base hash",
    "Hash base atual": "Current base hash", "Hash substituto": "Replacement hash",
    "ausente no pacote": "missing from package", "base mudou": "base changed", "base igual": "base unchanged",
    "Origem:": "Source:", "Pacote selecionado:": "Selected package:",
    "O pacote selecionado tem outro SHA-256.": "The selected package has a different SHA-256.",
    "O SHA-256 do pacote corresponde à origem.": "The package SHA-256 matches the source.",
    "Bases alteradas:": "Changed bases:", "caminhos ausentes:": "missing paths:",
    "Selecionar…": "Browse...", "Selecione a pasta de instalação": "Select game installation folder",
    "Pasta inválida": "Invalid folder", "Não encontrei essa pasta do jogo.": "Game folder not found.",
    "Nenhum pacote": "No packages", "Não encontrei arquivos .pak nessa pasta nem em data_packages.": "No .pak files found in this folder or its data_packages subfolder.",
    "Erro ao ler pacote": "Package read error", "Falha ao ler o pacote": "Failed to read package",
    "Selecione um arquivo": "Select a file", "Selecione um arquivo na lista primeiro.": "Select a file from the list first.",
    "Pasta de ferramentas inválida": "Invalid tools folder", "Falha ao salvar configuração": "Failed to save configuration",
    "Navegador indisponível": "Browser unavailable", "Não foi possível visualizar": "Unable to preview",
    "Falha ao decodificar MUNGED": "Failed to decode MUNGED", "Falha ao abrir prévia": "Failed to open preview",
    "Já está na área de trabalho": "Already in workspace", "Esse é o próprio arquivo da área de trabalho.": "That is already the workspace file.",
    "Aplicar frame editado": "Apply edited frame", "Validar área de trabalho": "Validate workspace",
    "Não foi possível validar": "Unable to validate", "Falha na validação": "Validation failed",
    "Relatório de validação": "Validation report", "Não foi possível criar perfil": "Unable to create profile",
    "Falha ao criar perfil": "Failed to create profile", "Não foi possível revisar perfil": "Unable to review profile",
    "Perfil incompatível": "Incompatible profile", "Não foi possível reaplicar perfil": "Unable to reapply profile",
    "Falha ao reaplicar perfil": "Failed to reapply profile", "Perfil reaplicado": "Profile reapplied",
    "Não foi possível reconstruir o pacote": "Unable to rebuild package", "Falha ao reconstruir PAK": "Failed to rebuild PAK",
    "Pacote candidato criado": "Candidate package created", "Concluído": "Complete", "Operação falhou": "Operation failed",
    "Substituição falhou": "Replacement failed", "Selecione o arquivo substituto": "Select replacement file",
    "Selecione a pasta avatar-legends-tools": "Select the avatar-legends-tools folder",
    "Salvar pacote candidato fora da pasta do jogo": "Save candidate package outside the game folder",
    "Salvar pacote reconstruído fora da pasta do jogo": "Save rebuilt package outside the game folder",
    "Salvar perfil de mod": "Save mod profile", "Abrir perfil de mod": "Open mod profile",
    "Pasta onde criar a exportação": "Folder for package export", "Escolha o arquivo substituto": "Choose replacement file",
    "Escolha o arquivo .munged editado": "Choose edited .munged file",
    "Pacote reconstruído": "Rebuilt package", "Pronto": "Ready",
}
EN.update({
    "Frame aplicado": "Frame staged", "Lote n\u00e3o aplicado": "Batch not applied",
    "Escolha a pasta do jogo e clique em Procurar .pak": "Choose the game folder and click Scan for .pak.",
    "Reaplicar perfil no workspace": "Reapply profile to workspace",
    "Falha ao decodificar movimento": "Failed to decode motion",
    "Alguns caminhos do perfil n\u00e3o existem no pacote selecionado.": "Some profile paths are missing from the selected package.",
    "Este pacote n\u00e3o cont\u00e9m frames de personagem reconhecidos.": "This package contains no recognized character frames.",
    "Falha ao ler o pacote": "Failed to read package",
    "Nenhum frame neste movimento.": "No frames in this motion.",
    "Aguarde a decodifica\u00e7\u00e3o dos frames.": "Wait for the frames to finish decoding.",
    "N\u00e3o encontrei .sprbin em srcdata/munged/scripts para as paletas deste pacote.": "No .sprbin files were found in srcdata/munged/scripts for this package's palettes.",
    "O arquivo selecionado n\u00e3o \u00e9 .munged.": "The selected file is not a .munged file.",
    "Selecione um arquivo .munged na lista.": "Select a .munged file from the list.",
    "Carregue o pacote de destino (incluindo a vers\u00e3o atualizada) antes de revisar.": "Load the destination package (including the updated version) before reviewing.",
    "O perfil ou sua pasta .assets j\u00e1 existe; escolha outro nome.": "The profile or its .assets folder already exists; choose another name.",
    "Formato ou vers\u00e3o de perfil n\u00e3o reconhecido.": "Unrecognized profile format or version.",
    "O perfil n\u00e3o cont\u00e9m altera\u00e7\u00f5es.": "The profile contains no changes.",
    "A \u00e1rea de trabalho n\u00e3o cont\u00e9m altera\u00e7\u00f5es para salvar.": "The workspace contains no changes to save.",
    "A \u00e1rea de trabalho precisa passar na valida\u00e7\u00e3o antes de criar o perfil.": "The workspace must pass validation before a profile can be created.",
    "O perfil tem nomes MUNGED repetidos; n\u00e3o \u00e9 poss\u00edvel validar em lote.": "The profile contains duplicate MUNGED names; batch validation is not possible.",
})

_PATTERNS = [
    (re.compile(r"^(\d+) de (\d+) arquivos$"), r"\1 of \2 files"),
    (re.compile(r"^Encontrados (\d+) pacotes \.pak$"), r"Found \1 .pak packages"),
    (re.compile(r"^Ferramentas carregadas de (.+)$"), r"Tools loaded from \1"),
    (re.compile(r"^O caminho salvo para avatar-legends-tools não é válido; selecione a nova pasta\.$"), "The saved avatar-legends-tools path is invalid; select the folder again."),
    (re.compile(r"^Lendo índice de (.+)…$"), r"Reading index: \1..."),
    (re.compile(r"^Lendo �ndice de (.+)�$"), r"Reading index: \1..."),
    (re.compile(r"^Pacote carregado: (\d+) arquivos; SHA-256 (.+)…$"), r"Package loaded: \1 files; SHA-256 \2..."),
    (re.compile(r"^Pacote carregado: (\d+) arquivos; SHA-256 (.+)�$"), r"Package loaded: \1 files; SHA-256 \2..."),
    (re.compile(r"^Extraindo…$"), "Extracting..."),
    (re.compile(r"^Criando pacote candidato…$"), "Creating candidate package..."),
    (re.compile(r"^Preparando prévia de (.+)…$"), r"Preparing preview: \1..."),
    (re.compile(r"^Preparando pr�via de (.+)�$"), r"Preparing preview: \1..."),
    (re.compile(r"^Prévia gerada: (.+)$"), r"Preview created: \1"),
    (re.compile(r"^Pr�via gerada: (.+)$"), r"Preview created: \1"),
    (re.compile(r"^Área de trabalho aberta: (.+)$"), r"Workspace opened: \1"),
    (re.compile(r"^�rea de trabalho aberta: (.+)$"), r"Workspace opened: \1"),
    (re.compile(r"^Pacote candidato criado: (.+)$"), r"Candidate package created: \1"),
    (re.compile(r"^Validando (\d+) arquivos substitutos…$"), r"Validating \1 replacement files..."),
    (re.compile(r"^Validando (\d+) arquivos substitutos�$"), r"Validating \1 replacement files..."),
    (re.compile(r"^Validando arquivos, frames MUNGED e inventário…$"), "Validating files, MUNGED frames, and inventory..."),
    (re.compile(r"^Validando arquivos, frames MUNGED e invent�rio�$"), "Validating files, MUNGED frames, and inventory..."),
    (re.compile(r"^Validação (APROVADO|FALHOU): (\d+) arquivos alterados$"), r"Validation \1: \2 changed files"),
    (re.compile(r"^Falha ao aplicar frame: (.+)$"), r"Failed to stage frame: \1"),
    (re.compile(r"^Validando e aplicando (\d+) substituições…$"), r"Validating and staging \1 replacements..."),
    (re.compile(r"^Perfil criado: (.+)$"), r"Profile created: \1"),
    (re.compile(r"^Perfil reaplicado no workspace: (\d+) arquivos$"), r"Profile reapplied to workspace: \1 files"),
    (re.compile(r"^Reaplicando perfil ao workspace…$"), "Reapplying profile to workspace..."),
    (re.compile(r"^Reconstruindo PAK a partir da área de trabalho…$"), "Rebuilding PAK from workspace..."),
    (re.compile(r"^Validação falhou: (.+)$"), r"Validation failed: \1"),
    (re.compile(r"^Valida��o falhou: (.+)$"), r"Validation failed: \1"),
    (re.compile(r"^Falha ao decodificar: (.+)$"), r"Decode failed: \1"),
    (re.compile(r"^Decodificando (\d+) frames de (.+) / (.+)…$"), r"Decoding \1 frames: \2 / \3..."),
    (re.compile(r"^Decodificando (\d+) frames de (.+) / (.+)�$"), r"Decoding \1 frames: \2 / \3..."),
    (re.compile(r"^Pronto: (\d+) frames decodificados\.$"), r"Ready: \1 frames decoded."),
    (re.compile(r"^Animações — (.+)$"), r"Animations - \1"),
    (re.compile(r"^Falha ao exibir frame: (.+)$"), r"Failed to display frame: \1"),
    (re.compile(r"^Falha ao criar perfil$"), "Failed to create profile"),
    (re.compile(r"^Frame editado aplicado \u00e0 \u00e1rea de trabalho; backup: (.+)$"), r"Edited frame staged in workspace; backup: \1"),
    (re.compile(r"^Ferramentas MUNGED salvas em (.+)$"), r"MUNGED tools saved to \1"),
    (re.compile(r"^Ferramentas configuradas para esta sess\u00e3o; n\u00e3o foi poss\u00edvel salvar: (.+)$"), r"Tools configured for this session; unable to save settings: \1"),
    (re.compile(r"^Candidato criado: (.+)$"), r"Candidate created: \1"),
    (re.compile(r"^Frame editado aplicado \u00e0 \u00e1rea de trabalho; backup: (.+)$"), r"Edited frame staged in workspace; backup: \1"),
    (re.compile(r"^Exporta\u00e7\u00e3o conclu\u00edda: (.+)$"), r"Export completed: \1"),
    (re.compile(r"^Falha ao gerar pr\u00e9via$"), "Failed to generate preview"),
]

_FRAGMENTS = {
    "Resultado: ": "Result: ", "APROVADO": "PASSED", "FALHOU": "FAILED",
    "Arquivos esperados/presentes:": "Expected/present files:", "Arquivos alterados:": "Changed files:",
    "Frames MUNGED alterados/decodificados:": "Changed/decoded MUNGED frames:",
    "Invent\u00e1rio e dados alterados est\u00e3o consistentes.": "The inventory and changed data are consistent.",
    "Vou guardar uma c\u00f3pia do frame atual e substituir este arquivo na \u00e1rea de trabalho:":
        "The current frame will be backed up and replaced in the workspace:",
    "Continuar?": "Continue?", "N\u00e3o encontrei estes scripts na pasta selecionada: ": "These scripts were not found in the selected folder: ",
    "N\u00e3o encontrei ": "Could not find ", "Configure a pasta raiz do projeto ": "Configure the project root folder ",
    "Valide e reconstrua um novo .pak quando estiver pronto.": "Validate and rebuild a new .pak when ready.",
    "Pr\u00e9-valida\u00e7\u00e3o, \u00edndice e hashes dos payloads conferidos.": "Pre-validation, index, and payload hashes checked.",
    "Compatibilidade no jogo ainda n\u00e3o testada.": "In-game compatibility has not been tested.",
    "Compatibilidade no jogo ainda n\u00e3o foi testada.": "In-game compatibility has not been tested.",
    "Origem:": "Source:", "Pacote selecionado:": "Selected package:",
    "O pacote selecionado tem outro SHA-256.": "The selected package has a different SHA-256.",
    "O SHA-256 do pacote corresponde \u00e0 origem.": "The package SHA-256 matches the source.",
    "Bases alteradas:": "Changed bases:", "caminhos ausentes:": "missing paths:",
    "Mantenha junto a pasta .assets para revisar ou reaplicar.": "Keep the .assets folder with the profile to review or reapply it.",
    "Arquivos: ": "Files: ", "SHA-256: ": "SHA-256: ", "Arquivo: ": "File: ",
    "Tamanho esperado: ": "Expected size: ", "SHA-256 novo asset: ": "Replacement asset SHA-256: ",
    "O jogo ainda n\u00e3o foi usado para validar este pacote.": "The game has not been used to validate this package.",
    "Arquivos extra\u00eddos para:\n": "Files extracted to:\\n",
}

_PT_FIXES = {
    "Selecionar�": "Selecionar...", "Extrair pacote�": "Extrair pacote...",
    "Substituir arquivo selecionado�": "Substituir arquivo selecionado...",
    "Configurar ferramentas MUNGED�": "Configurar ferramentas MUNGED...",
    "Navegar anima��es�": "Navegar animações...", "Aplicar MUNGED editado�": "Aplicar MUNGED editado...",
    "Validar �rea de trabalho": "Validar área de trabalho", "Reconstruir pacote modificado�": "Reconstruir pacote modificado...",
    "Idioma:": "Idioma:", "Inglês": "Inglês",
    "Aplicar substitutos selecionados�": "Aplicar substitutos selecionados...",
    "Frames em ordem natural (Ctrl/Shift para selecionar)": "Frames em ordem natural (Ctrl/Shift para selecionar)",
    "Navegador indispon�vel": "Navegador indisponível", "Pasta inv�lida": "Pasta inválida",
}

def _repair_legacy_text(value: str) -> str:
    """Normalize common mojibake spellings in older interface literals."""
    pairs = {
        "\u00c3\u00a1": "\u00e1", "\u00c3\u00a9": "\u00e9", "\u00c3\u00ad": "\u00ed",
        "\u00c3\u00b3": "\u00f3", "\u00c3\u00ba": "\u00fa", "\u00c3\u00a3": "\u00e3",
        "\u00c3\u00b5": "\u00f5", "\u00c3\u00a7": "\u00e7", "\u00c3\u0081": "\u00c1",
        "\u00c3\u2030": "\u00c9", "\u00c3\u008d": "\u00cd", "\u00c3\u0093": "\u00d3",
        "\u00c3\u009a": "\u00da", "\u00c3\u0087": "\u00c7", "\u00c3\u00aa": "\u00ea",
        "\u00c3\u00b4": "\u00f4", "\u00c3\u00a0": "\u00e0", "\u00c3\u00bc": "\u00fc",
        "\u00e2\u20ac\u00a6": "\u2026", "\u00e2\u20ac\u201d": "\u2014",
        "\u00e2\u20ac\u201c": "\u201c", "\u00e2\u20ac\u009d": "\u201d",
    }
    for old, new in pairs.items():
        value = value.replace(old, new)
    return value


EN = {_repair_legacy_text(key): _repair_legacy_text(value) for key, value in EN.items()}
_PATTERNS = [(re.compile(_repair_legacy_text(pattern.pattern), pattern.flags), _repair_legacy_text(replacement)) for pattern, replacement in _PATTERNS]


def set_language(language: str) -> None:
    global LANGUAGE
    LANGUAGE = language if language in {"en", "pt"} else "en"


def tr(value):
    if not isinstance(value, str):
        return value
    if LANGUAGE == "pt":
        return _PT_FIXES.get(value, value)
    value_for_lookup = _repair_legacy_text(value)
    translated = EN.get(value_for_lookup)
    if translated is not None:
        return translated
    for pattern, replacement in _PATTERNS:
        if pattern.match(value_for_lookup):
            return pattern.sub(replacement, value_for_lookup)
    value = value_for_lookup
    for source, target in _FRAGMENTS.items():
        value = value.replace(source, target)
    return value


def install() -> None:
    """Translate common Tk widget labels, dialog titles, and StringVar status text."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    if getattr(install, "installed", False):
        return
    install.installed = True

    for name in ("Label", "Button", "Checkbutton", "Radiobutton", "Labelframe"):
        original = getattr(ttk, name)
        def make_factory(factory):
            def translated_factory(*args, **kwargs):
                for key in ("text", "label", "title"):
                    if key in kwargs:
                        kwargs[key] = tr(kwargs[key])
                return factory(*args, **kwargs)
            return translated_factory
        setattr(ttk, name, make_factory(original))

    original_heading = ttk.Treeview.heading
    def heading(widget, column, option=None, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = tr(kwargs["text"])
        return original_heading(widget, column, option, **kwargs)
    ttk.Treeview.heading = heading

    original_insert = ttk.Treeview.insert
    def insert(widget, parent, index, iid=None, **kwargs):
        if "values" in kwargs:
            kwargs["values"] = tuple(tr(value) for value in kwargs["values"])
        return original_insert(widget, parent, index, iid=iid, **kwargs)
    ttk.Treeview.insert = insert

    original_configure = ttk.Widget.configure
    def configure(widget, cnf=None, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = tr(kwargs["text"])
        return original_configure(widget, cnf, **kwargs)
    ttk.Widget.configure = configure

    original_set = tk.StringVar.set
    def localized_set(variable, value):
        return original_set(variable, tr(value))
    tk.StringVar.set = localized_set

    for method in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel"):
        original = getattr(messagebox, method)
        def make_dialog(fn):
            def translated_dialog(title, message, *args, **kwargs):
                return fn(tr(title), tr(message), *args, **kwargs)
            return translated_dialog
        setattr(messagebox, method, make_dialog(original))
    for method in ("askdirectory", "askopenfilename", "asksaveasfilename", "askopenfilenames"):
        original = getattr(filedialog, method)
        def make_file_dialog(fn):
            def translated_dialog(*args, **kwargs):
                if "title" in kwargs:
                    kwargs["title"] = tr(kwargs["title"])
                return fn(*args, **kwargs)
            return translated_dialog
        setattr(filedialog, method, make_file_dialog(original))

    for cls in (tk.Tk, tk.Toplevel):
        original_title = cls.title
        def make_title(fn):
            def translated_title(window, text=None):
                if text is None:
                    return fn(window)
                return fn(window, tr(text))
            return translated_title
        cls.title = make_title(original_title)
