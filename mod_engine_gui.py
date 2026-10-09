#!/usr/bin/env python3
"""Simple graphical front-end for the Avatar Legends PACK tools."""

from __future__ import annotations

import queue
import configparser
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import tempfile
from datetime import datetime
import tkinter as tk
from pathlib import Path, PurePosixPath
from tkinter import filedialog, messagebox, ttk

import pak_probe
import mod_profile
import localization


DEFAULT_GAME = Path(r"G:\SteamLibrary\steamapps\common\Avatar Legends The Fighting Game")
CONFIG_FILE = Path(__file__).resolve().with_name("mod_engine.ini")


def run_tool(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "sem mensagem")[-2400:]
        raise RuntimeError(f"Ferramenta terminou com código {result.returncode}: {detail}")
    return result


class ModEngineGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Avatar Legends Mod Engine")
        self.geometry("1280x720")
        self.minsize(980, 560)

        self.game_dir = tk.StringVar(value=str(DEFAULT_GAME))
        self.filter_text = tk.StringVar()
        self.tools_dir = tk.StringVar(value=self._load_tools_dir())
        self.language = tk.StringVar(value=self._load_language())
        localization.set_language(self.language.get())
        localization.install()
        self.status = tk.StringVar(value="Escolha a pasta do jogo e clique em Procurar .pak")
        self.packages: list[Path] = []
        self.current_package: dict[str, object] | None = None
        self.entries_by_iid: dict[str, dict[str, object]] = {}
        self.results: queue.Queue = queue.Queue()

        self._build()
        if self.tools_dir.get():
            saved_tools = Path(self.tools_dir.get())
            if saved_tools.is_dir() and (saved_tools / "munged_extract.py").is_file() and (saved_tools / "pak_pack.py").is_file():
                self.status.set(f"Ferramentas carregadas de {saved_tools}")
            else:
                self.status.set("O caminho salvo para avatar-legends-tools não é válido; selecione a nova pasta.")
        self.after(100, self._poll_results)

    @staticmethod
    def _load_tools_dir() -> str:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(CONFIG_FILE, encoding="utf-8")
            return parser.get("tools", "directory", fallback="")
        except (configparser.Error, OSError):
            return ""

    @staticmethod
    def _save_tools_dir(directory: str) -> None:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(CONFIG_FILE, encoding="utf-8")
        if not parser.has_section("tools"):
            parser.add_section("tools")
        parser.set("tools", "directory", directory)
        with CONFIG_FILE.open("w", encoding="utf-8", newline="\n") as stream:
            parser.write(stream)

    @staticmethod
    def _load_language() -> str:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(CONFIG_FILE, encoding="utf-8")
            language = parser.get("ui", "language", fallback="en").lower()
            return language if language in {"en", "pt"} else "en"
        except (configparser.Error, OSError):
            return "en"

    @staticmethod
    def _save_language(language: str) -> None:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(CONFIG_FILE, encoding="utf-8")
        if not parser.has_section("ui"):
            parser.add_section("ui")
        parser.set("ui", "language", language)
        with CONFIG_FILE.open("w", encoding="utf-8", newline="\n") as stream:
            parser.write(stream)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Pasta do jogo:").grid(row=0, column=0, sticky="w")
        ttk.Entry(root, textvariable=self.game_dir).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(root, text="Selecionar…", command=self._choose_game).grid(row=0, column=2, padx=3)
        ttk.Button(root, text="Procurar .pak", command=self._scan).grid(row=0, column=3, padx=3)
        language_frame = ttk.Frame(root)
        language_frame.grid(row=0, column=4, sticky="e", padx=(12, 0))
        ttk.Label(language_frame, text="Idioma:").pack(side="left", padx=(0, 5))
        language_values = ("English", "Português") if self.language.get() == "en" else ("Inglês", "Português")
        self.language_box = ttk.Combobox(language_frame, state="readonly", width=11, values=language_values)
        self.language_box.set(language_values[0] if self.language.get() == "en" else language_values[1])
        self.language_box.pack(side="left")
        self.language_box.bind("<<ComboboxSelected>>", self._change_language)

        ttk.Label(root, text="Pacote:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.package_box = ttk.Combobox(root, state="readonly")
        self.package_box.grid(row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=(10, 0))
        self.package_box.bind("<<ComboboxSelected>>", self._load_package)

        ttk.Label(root, text="Filtro de caminho:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        filter_entry = ttk.Entry(root, textvariable=self.filter_text)
        filter_entry.grid(row=2, column=1, sticky="ew", padx=8, pady=(10, 0))
        filter_entry.bind("<KeyRelease>", lambda _event: self._populate_entries())
        self.count_label = ttk.Label(root, text="Nenhum pacote carregado")
        self.count_label.grid(row=2, column=2, columnspan=2, sticky="e", pady=(10, 0))

        columns = ("path", "size", "offset")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("path", text="Arquivo dentro do pacote")
        self.tree.heading("size", text="Tamanho (bytes)")
        self.tree.heading("offset", text="Offset")
        self.tree.column("path", width=600, anchor="w")
        self.tree.column("size", width=130, anchor="e")
        self.tree.column("offset", width=130, anchor="e")
        self.tree.grid(row=3, column=0, columnspan=4, sticky="nsew", pady=10)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=3, column=4, sticky="ns", pady=10)
        self.tree.configure(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(root)
        buttons.grid(row=4, column=0, columnspan=4, sticky="w")
        ttk.Button(buttons, text="Extrair pacote…", command=self._extract).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Substituir arquivo selecionado…", command=self._replace).pack(side="left")

        frame_tools = ttk.Frame(root)
        frame_tools.grid(row=5, column=0, columnspan=4, sticky="w", pady=(9, 0))
        ttk.Button(frame_tools, text="Configurar ferramentas MUNGED…", command=self._choose_tools).pack(side="left", padx=(0, 8))
        ttk.Button(frame_tools, text="Visualizar frame MUNGED", command=self._preview_munged).pack(side="left", padx=(0, 8))
        ttk.Button(frame_tools, text="Navegar animações…", command=self._open_animation_browser).pack(side="left", padx=(0, 8))
        ttk.Button(frame_tools, text="Aplicar MUNGED editado…", command=self._stage_munged).pack(side="left", padx=(0, 8))
        ttk.Button(frame_tools, text="Abrir pasta de trabalho", command=self._open_workspace).pack(side="left", padx=(0, 8))
        ttk.Button(frame_tools, text="Validar área de trabalho", command=self._validate_workspace).pack(side="left", padx=(0, 8))
        ttk.Button(frame_tools, text="Reconstruir pacote modificado…", command=self._rebuild_package).pack(side="left")

        profiles = ttk.Frame(root)
        profiles.grid(row=6, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(profiles, text="Criar perfil de mod...", command=self._create_mod_profile).pack(side="left", padx=(0, 8))
        ttk.Button(profiles, text="Revisar/Reaplicar perfil...", command=self._review_mod_profile).pack(side="left")

        note = ttk.Label(
            root,
            text="Para frames .munged, configure a pasta do projeto avatar-legends-tools. A GUI extrai para uma área de trabalho, "
                 "abre a prévia PNG e reconstrói um .pak novo; ela nunca altera o pacote instalado.",
            wraplength=920,
            foreground="#7a4b00",
        )
        note.grid(row=7, column=0, columnspan=4, sticky="w", pady=(7, 4))
        ttk.Label(root, textvariable=self.status).grid(row=8, column=0, columnspan=4, sticky="w")
        root.columnconfigure(1, weight=1)
        root.rowconfigure(3, weight=1)

    def _change_language(self, _event=None) -> None:
        language = "pt" if self.language_box.get() == "Português" else "en"
        if language == self.language.get():
            return
        try:
            self._save_language(language)
        except OSError as exc:
            messagebox.showerror("Falha ao salvar configuração", str(exc))
            values = ("English", "Português") if self.language.get() == "en" else ("Inglês", "Português")
            self.language_box.configure(values=values)
            self.language_box.set(values[0] if self.language.get() == "en" else values[1])
            return
        self.language.set(language)
        localization.set_language(language)
        for child in self.winfo_children():
            close_window = getattr(child, "_close", None)
            if callable(close_window):
                close_window()
            else:
                child.destroy()
        self._build()
        self.package_box["values"] = [path.name for path in self.packages]
        if self.current_package:
            for index, path in enumerate(self.packages):
                if str(path.resolve()) == self.current_package["path"]:
                    self.package_box.current(index)
                    break
            self._populate_entries()
        self.status.set("Idioma alterado." if language == "pt" else "Language changed.")

    def _choose_game(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta de instalação")
        if selected:
            self.game_dir.set(selected)

    def _scan(self) -> None:
        folder = Path(self.game_dir.get())
        if not folder.is_dir():
            messagebox.showerror("Pasta inválida", "Não encontrei essa pasta do jogo.")
            return
        package_dir = folder / "data_packages"
        packages = sorted(package_dir.glob("*.pak")) if package_dir.is_dir() else sorted(folder.glob("*.pak"))
        if not packages:
            messagebox.showinfo("Nenhum pacote", "Não encontrei arquivos .pak nessa pasta nem em data_packages.")
            return
        self.packages = packages
        self.package_box["values"] = [p.name for p in packages]
        self.package_box.current(0)
        self._load_package()
        self.status.set(f"Encontrados {len(packages)} pacotes .pak")

    def _load_package(self, _event=None) -> None:
        index = self.package_box.current()
        if index < 0 or index >= len(self.packages):
            return
        package_path = self.packages[index]
        self.status.set(f"Lendo índice de {package_path.name}…")
        self._run_background(lambda: pak_probe.parse_package(package_path), self._package_loaded)

    def _package_loaded(self, result) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Erro ao ler pacote", str(result))
            self.status.set("Falha ao ler o pacote")
            return
        self.current_package = result
        self._populate_entries()
        self.status.set(f"Pacote carregado: {result['record_count']} arquivos; SHA-256 {result['sha256'][:16]}…")

    def _populate_entries(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.entries_by_iid.clear()
        if not self.current_package:
            return
        needle = self.filter_text.get().casefold().strip()
        shown = 0
        for entry in self.current_package["entries"]:
            if needle and needle not in entry["path"].casefold():
                continue
            iid = self.tree.insert("", "end", values=(entry["path"], entry["payload_size"], entry["payload_offset"]))
            self.entries_by_iid[iid] = entry
            shown += 1
        self.count_label.configure(text=f"{shown} de {self.current_package['record_count']} arquivos")

    def _extract(self) -> None:
        if not self.current_package:
            return
        destination = filedialog.askdirectory(title="Pasta onde criar a exportação")
        if not destination:
            return
        package = self.current_package
        self.status.set("Extraindo…")
        self._run_background(lambda: pak_probe.extract_package(package, Path(destination)), self._operation_done)

    def _replace(self) -> None:
        if not self.current_package:
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Selecione um arquivo", "Selecione um arquivo na lista primeiro.")
            return
        entry = self.entries_by_iid[selected[0]]
        source = filedialog.askopenfilename(title="Escolha o arquivo substituto")
        if not source:
            return
        output = filedialog.asksaveasfilename(
            title="Salvar pacote candidato fora da pasta do jogo",
            defaultextension=".pak",
            initialfile=f"{Path(self.current_package['path']).stem}-mod.pak",
            filetypes=(("Pacote PAK", "*.pak"),),
        )
        if not output:
            return
        package = self.current_package
        self.status.set("Criando pacote candidato…")

        def work():
            return pak_probe.replace_same_size(package, entry["path"], Path(source), Path(output))

        self._run_background(work, self._replacement_done)

    def _choose_tools(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta avatar-legends-tools")
        if selected:
            folder = Path(selected)
            missing = [name for name in ("munged_extract.py", "pak_pack.py") if not (folder / name).is_file()]
            if missing:
                messagebox.showerror(
                    "Pasta de ferramentas inválida",
                    "Não encontrei estes scripts na pasta selecionada: " + ", ".join(missing),
                )
                return
            self.tools_dir.set(str(folder.resolve()))
            try:
                self._save_tools_dir(self.tools_dir.get())
                self.status.set(f"Ferramentas MUNGED salvas em {CONFIG_FILE}")
            except OSError as exc:
                self.status.set(f"Ferramentas configuradas para esta sessão; não foi possível salvar: {exc}")
                messagebox.showerror("Falha ao salvar configuração", str(exc))

    def _tools_script(self, name: str) -> Path:
        folder = Path(self.tools_dir.get())
        script = folder / name
        if not folder.is_dir() or not script.is_file():
            raise FileNotFoundError(
                f"Não encontrei {name}. Configure a pasta raiz do projeto "
                "avatar-legends-tools em ‘Configurar ferramentas MUNGED…’."
            )
        return script

    def _workspace(self) -> Path:
        if not self.current_package:
            raise ValueError("Carregue um pacote primeiro.")
        package_path = Path(self.current_package["path"])
        folder = Path(__file__).resolve().parent / "workspaces" / f"{package_path.stem}_{self.current_package['sha256'][:8]}"
        package_root = folder / package_path.stem
        manifest = folder / f"{package_path.stem}.export-manifest.json"
        if package_root.is_dir() and manifest.is_file():
            return package_root
        if package_root.exists() or manifest.exists():
            raise FileExistsError(f"Área de trabalho incompleta em {folder}; revise-a antes de continuar.")
        folder.mkdir(parents=True, exist_ok=True)
        pak_probe.extract_package(self.current_package, folder)
        return package_root

    def _selected_munged(self):
        if not self.current_package:
            raise ValueError("Carregue um pacote primeiro.")
        selection = self.tree.selection()
        if not selection:
            raise ValueError("Selecione um arquivo .munged na lista.")
        entry = self.entries_by_iid[selection[0]]
        if not entry["path"].lower().endswith(".munged"):
            raise ValueError("O arquivo selecionado não é .munged.")
        return entry

    def _preview_munged(self) -> None:
        try:
            entry = self._selected_munged()
            decoder = self._tools_script("munged_extract.py")
            package = self.current_package
            self.status.set(f"Preparando prévia de {entry['path']}…")

            def work():
                package_root = self._workspace()
                munged_file = package_root.joinpath(*Path(entry["path"]).parts)
                if not munged_file.is_file():
                    raise FileNotFoundError(f"Frame não encontrado na área extraída: {munged_file}")
                previews = package_root.parent / ".mod_engine_previews"
                previews.mkdir(exist_ok=True)
                output = Path(tempfile.mkdtemp(prefix="frame_", dir=previews))
                result = run_tool(
                    [os.fspath(Path(os.sys.executable)), os.fspath(decoder), os.fspath(munged_file), os.fspath(output), "--auto-palette"]
                )
                images = sorted(output.rglob("*.png"))
                if not images:
                    raise RuntimeError("O decodificador terminou sem gerar PNG. " + result.stderr[-1200:])
                return images[0]

            self._run_background(work, self._preview_done)
        except Exception as exc:
            messagebox.showerror("Não foi possível visualizar", str(exc))

    def _open_animation_browser(self) -> None:
        if not self.current_package:
            messagebox.showinfo("Nenhum pacote", "Carregue um pacote primeiro.")
            return
        try:
            decoder = self._tools_script("munged_extract.py")
            workspace = self._workspace()
            AnimationBrowser(self, self.current_package, workspace, decoder)
        except Exception as exc:
            messagebox.showerror("Navegador indisponível", str(exc))

    def _preview_done(self, result) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Falha ao decodificar MUNGED", str(result))
            self.status.set("Falha ao gerar prévia")
            return
        try:
            window = tk.Toplevel(self)
            window.title(result.name)
            window.geometry("900x700")
            image = tk.PhotoImage(file=os.fspath(result))
            scale = max(1, (image.width() + 840 - 1) // 840, (image.height() + 600 - 1) // 600)
            if scale > 1:
                image = image.subsample(scale, scale)
            canvas = tk.Canvas(window, background="#303030")
            xbar = ttk.Scrollbar(window, orient="horizontal", command=canvas.xview)
            ybar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
            canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            ybar.grid(row=0, column=1, sticky="ns")
            xbar.grid(row=1, column=0, sticky="ew")
            canvas.create_image(0, 0, anchor="nw", image=image)
            canvas.configure(scrollregion=(0, 0, image.width(), image.height()))
            canvas.image = image
            window.columnconfigure(0, weight=1)
            window.rowconfigure(0, weight=1)
            self.status.set(f"Prévia gerada: {result}")
        except Exception as exc:
            messagebox.showerror("Falha ao abrir prévia", str(exc))

    def _open_workspace(self) -> None:
        try:
            package_root = self._workspace()
            os.startfile(os.fspath(package_root))
            self.status.set(f"Área de trabalho aberta: {package_root}")
        except Exception as exc:
            messagebox.showerror("Área de trabalho indisponível", str(exc))

    def _stage_munged(self) -> None:
        try:
            entry = self._selected_munged()
            package_root = self._workspace()
            destination = package_root.joinpath(*Path(entry["path"]).parts)
            replacement = filedialog.askopenfilename(
                title="Escolha o arquivo .munged editado",
                filetypes=(("Abare MUNGED", "*.munged"), ("Todos os arquivos", "*.*")),
            )
            if not replacement:
                return
            replacement_path = Path(replacement).resolve()
            if replacement_path == destination.resolve():
                messagebox.showinfo("Já está na área de trabalho", "Esse é o próprio arquivo da área de trabalho.")
                return
            if not messagebox.askyesno(
                "Aplicar frame editado",
                f"Vou guardar uma cópia do frame atual e substituir este arquivo na área de trabalho:\n\n{entry['path']}\n\nContinuar?",
            ):
                return
            backup_dir = package_root.parent / ".mod_engine_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            changes_path = package_root.parent / ".mod_engine_changes.json"
            changes = json.loads(changes_path.read_text(encoding="utf-8")) if changes_path.is_file() else {"changes": []}
            prior = {item["path"]: item for item in changes.get("changes", [])}
            prior_item = prior.get(str(entry["path"]), {})
            backup = Path(prior_item["backup"]) if prior_item.get("backup") and Path(prior_item["backup"]).is_file() else backup_dir / f"{destination.name}.{stamp}.bak"
            if not backup.exists():
                shutil.copy2(destination, backup)
            shutil.copy2(replacement_path, destination)
            export_manifest = json.loads((package_root.parent / f"{Path(self.current_package['path']).stem}.export-manifest.json").read_text(encoding="utf-8"))
            original_hash = next(item["sha256"] for item in export_manifest["entries"] if item["path"] == entry["path"])
            prior[str(entry["path"])] = {
                "path": str(entry["path"]),
                "original_sha256": original_hash,
                "staged_sha256": pak_probe.sha256_file(destination),
                "replacement_source": str(replacement_path),
                "backup": str(backup),
                "updated_at": stamp,
            }
            changes["changes"] = list(prior.values())
            changes_path.write_text(json.dumps(changes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.status.set(f"Frame editado aplicado à área de trabalho; backup: {backup}")
            messagebox.showinfo(
                "Frame aplicado",
                f"O arquivo editado está na área de trabalho e será incluído no próximo PAK reconstruído.\n\nBackup:\n{backup}",
            )
        except Exception as exc:
            messagebox.showerror("Falha ao aplicar frame", str(exc))

    def _stage_munged_batch(self, package: dict[str, object], package_root: Path, entries, replacement_dir: Path, callback) -> None:
        try:
            decoder = self._tools_script("munged_extract.py")
            if not replacement_dir.is_dir():
                raise NotADirectoryError(replacement_dir)
            self.status.set(f"Validando e aplicando {len(entries)} substituições…")

            def work():
                replacements = list(replacement_dir.rglob("*.munged"))
                by_name = {}
                for path in replacements:
                    by_name.setdefault(path.name.casefold(), []).append(path)
                selected = []
                used_sources = set()
                for entry in entries:
                    internal_name = PurePosixPath(str(entry["path"])).name
                    candidates = by_name.get(internal_name.casefold(), [])
                    if not candidates and entry.get("frame_name"):
                        candidates = by_name.get(f"{entry['frame_name']}.munged".casefold(), [])
                    if len(candidates) != 1:
                        raise ValueError(f"Substituto ausente ou ambíguo para {entry.get('frame_name', internal_name)}.")
                    source = candidates[0].resolve()
                    if source in used_sources:
                        raise ValueError(f"O mesmo arquivo substituto foi associado a mais de um frame: {source.name}")
                    used_sources.add(source)
                    destination = package_root.joinpath(*PurePosixPath(str(entry["path"])).parts)
                    if source == destination.resolve():
                        raise ValueError(f"O substituto selecionado já é o arquivo de destino: {internal_name}")
                    selected.append((entry, source, destination))

                preview_root = package_root.parent / ".mod_engine_previews"
                preview_root.mkdir(exist_ok=True)
                run_dir = Path(tempfile.mkdtemp(prefix="batch_validate_", dir=preview_root))
                input_dir, output_dir = run_dir / "input", run_dir / "output"
                input_dir.mkdir()
                output_dir.mkdir()
                for entry, source, _destination in selected:
                    internal_name = PurePosixPath(str(entry["path"])).name
                    shutil.copy2(source, input_dir / internal_name)
                run_tool([os.fspath(Path(os.sys.executable)), os.fspath(decoder), os.fspath(input_dir), os.fspath(output_dir)])
                decoded_stems = {path.stem.casefold() for path in output_dir.rglob("*.png")}
                missing_decodes = [
                    PurePosixPath(str(entry["path"])).stem
                    for entry, _source, _destination in selected
                    if PurePosixPath(str(entry["path"])).stem.casefold() not in decoded_stems
                ]
                if missing_decodes:
                    raise ValueError(f"O decodificador não abriu estes frames: {missing_decodes[:8]}")

                backup_dir = package_root.parent / ".mod_engine_backups"
                backup_dir.mkdir(exist_ok=True)
                changes_path = package_root.parent / ".mod_engine_changes.json"
                changes = json.loads(changes_path.read_text(encoding="utf-8")) if changes_path.is_file() else {"changes": []}
                prior = {item["path"]: item for item in changes.get("changes", [])}
                export_manifest_path = package_root.parent / f"{Path(package['path']).stem}.export-manifest.json"
                export_manifest = json.loads(export_manifest_path.read_text(encoding="utf-8"))
                original_hashes = {item["path"]: item["sha256"] for item in export_manifest["entries"]}
                staged_backups = []
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                for entry, source, destination in selected:
                    old_backup = prior.get(str(entry["path"]), {}).get("backup")
                    backup = Path(old_backup) if old_backup and Path(old_backup).is_file() else backup_dir / f"{destination.name}.{stamp}.bak"
                    if not backup.exists():
                        shutil.copy2(destination, backup)
                    rollback_copy = backup_dir / f"{destination.name}.{stamp}.rollback"
                    shutil.copy2(destination, rollback_copy)
                    staged_backups.append((entry, source, destination, backup, rollback_copy))
                applied = []
                try:
                    for entry, source, destination, backup, rollback_copy in staged_backups:
                        shutil.copy2(source, destination)
                        applied.append((destination, rollback_copy))
                except Exception:
                    for destination, backup in reversed(applied):
                        shutil.copy2(backup, destination)
                    raise
                else:
                    for _entry, _source, _destination, _backup, rollback_copy in staged_backups:
                        rollback_copy.unlink(missing_ok=True)

                for entry, source, destination, backup, _rollback_copy in staged_backups:
                    prior[str(entry["path"])] = {
                        "path": str(entry["path"]),
                        "original_sha256": original_hashes.get(str(entry["path"])),
                        "staged_sha256": pak_probe.sha256_file(destination),
                        "replacement_source": str(source),
                        "backup": str(backup),
                        "updated_at": stamp,
                    }
                changes["changes"] = list(prior.values())
                changes_path.write_text(json.dumps(changes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                return {"count": len(selected), "paths": [str(entry["path"]) for entry, _source, _destination in selected]}

            self._run_background(work, callback)
        except Exception as exc:
            callback(exc)

    def _validate_workspace(self) -> None:
        if not self.current_package:
            messagebox.showinfo("Nenhum pacote", "Carregue um pacote primeiro.")
            return
        try:
            decoder = self._tools_script("munged_extract.py")
            package = self.current_package
            package_root = self._workspace()
            self.status.set("Validando arquivos, frames MUNGED e inventário…")

            def work():
                return self._validate_workspace_contents(package, package_root, decoder)

            self._run_background(work, self._validation_done)
        except Exception as exc:
            messagebox.showerror("Não foi possível validar", str(exc))

    def _validate_workspace_contents(self, package: dict[str, object], package_root: Path, decoder: Path) -> dict[str, object]:
        source = Path(package["path"])
        manifest_path = package_root.parent / f"{source.stem}.export-manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Manifesto original ausente: {manifest_path}")
        export_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        original_entries = {entry["path"]: entry for entry in export_manifest["entries"]}
        expected_paths = set(original_entries)
        errors = []
        if export_manifest.get("source_sha256") != package["sha256"]:
            errors.append("O hash do pacote no manifesto não corresponde ao pacote selecionado.")
        if expected_paths != {entry["path"] for entry in package["entries"]}:
            errors.append("O manifesto de extração não corresponde ao índice do pacote selecionado.")
        actual_files = [path for path in package_root.rglob("*") if path.is_file()]
        actual_paths = {path.relative_to(package_root).as_posix() for path in actual_files}
        missing = sorted(expected_paths - actual_paths)
        unexpected = sorted(actual_paths - expected_paths)
        hashes = {}
        changed_munged = []
        changed_files = 0
        for relative in sorted(expected_paths & actual_paths):
            path = package_root.joinpath(*PurePosixPath(relative).parts)
            digest = pak_probe.sha256_file(path)
            hashes[relative] = {"sha256": digest, "size": path.stat().st_size}
            if digest != original_entries[relative]["sha256"]:
                changed_files += 1
                if relative.lower().endswith(".munged"):
                    changed_munged.append((relative, path))
        if missing:
            errors.append(f"Faltam arquivos esperados: {missing[:8]}")
        if unexpected:
            errors.append(f"Há arquivos fora do índice original: {unexpected[:8]}")

        decoded_count = 0
        if changed_munged:
            preview_root = package_root.parent / ".mod_engine_previews"
            preview_root.mkdir(exist_ok=True)
            run_dir = Path(tempfile.mkdtemp(prefix="validate_", dir=preview_root))
            input_dir, output_dir = run_dir / "input", run_dir / "output"
            input_dir.mkdir()
            output_dir.mkdir()
            stems = {}
            for relative, path in changed_munged:
                name = PurePosixPath(relative).name
                stem = PurePosixPath(name).stem.casefold()
                if stem in stems:
                    raise ValueError(f"Nomes de frame repetidos impedem a validação em lote: {stems[stem]} e {relative}")
                stems[stem] = relative
                shutil.copy2(path, input_dir / name)
            run_tool([os.fspath(Path(os.sys.executable)), os.fspath(decoder), os.fspath(input_dir), os.fspath(output_dir)])
            decoded_stems = {path.stem.casefold() for path in output_dir.rglob("*.png")}
            not_decoded = [relative for stem, relative in stems.items() if stem not in decoded_stems]
            decoded_count = len(stems) - len(not_decoded)
            if not_decoded:
                errors.append(f"Frames MUNGED que não geraram PNG: {not_decoded[:8]}")

        return {
            "valid": not errors,
            "package": str(source),
            "expected_count": len(expected_paths),
            "actual_count": len(actual_paths),
            "changed_count": changed_files,
            "changed_munged_count": len(changed_munged),
            "decoded_munged_count": decoded_count,
            "missing": missing,
            "unexpected": unexpected,
            "errors": errors,
            "hashes": hashes,
            "source_sha256": package["sha256"],
        }

    def _validation_done(self, result) -> None:
        if isinstance(result, Exception):
            self.status.set(f"Validação falhou: {result}")
            messagebox.showerror("Falha na validação", str(result))
            return
        state = "APROVADO" if result["valid"] else "FALHOU"
        self.status.set(f"Validação {state}: {result['changed_count']} arquivos alterados")
        details = "\n".join(result["errors"]) if result["errors"] else "Inventário e dados alterados estão consistentes."
        report = (
            f"Resultado: {state}\n"
            f"Arquivos esperados/presentes: {result['expected_count']}/{result['actual_count']}\n"
            f"Arquivos alterados: {result['changed_count']}\n"
            f"Frames MUNGED alterados/decodificados: {result['changed_munged_count']}/{result['decoded_munged_count']}\n\n"
            f"{details}"
        )
        (messagebox.showinfo if result["valid"] else messagebox.showerror)("Relatório de validação", report)

    def _create_mod_profile(self) -> None:
        if not self.current_package:
            messagebox.showinfo("Nenhum pacote", "Carregue um pacote primeiro.")
            return
        try:
            decoder = self._tools_script("munged_extract.py")
            package, workspace = self.current_package, self._workspace()
            profiles_dir = Path(__file__).resolve().parent / "profiles"
            profiles_dir.mkdir(exist_ok=True)
            target = filedialog.asksaveasfilename(
                title="Salvar perfil de mod", initialdir=str(profiles_dir),
                initialfile=f"{Path(package['path']).stem}-mod.modprofile.json",
                defaultextension=".modprofile.json", filetypes=(("Perfil de mod", "*.modprofile.json"),),
            )
            if not target:
                return
            profile_path = Path(target).resolve()
            assets_dir = profile_path.with_name(profile_path.stem + ".assets")
            if profile_path.exists() or assets_dir.exists():
                raise FileExistsError("O perfil ou sua pasta .assets já existe; escolha outro nome.")
            self.status.set("Validando alterações e criando perfil...")
            def work():
                validation = self._validate_workspace_contents(package, workspace, decoder)
                profile = mod_profile.create_profile(profile_path, package, workspace, validation)
                return {"path": str(profile_path), "count": len(profile["changes"])}
            self._run_background(work, self._profile_created)
        except Exception as exc:
            messagebox.showerror("Não foi possível criar perfil", str(exc))

    def _profile_created(self, result) -> None:
        if isinstance(result, Exception):
            self.status.set("Falha ao criar perfil")
            messagebox.showerror("Falha ao criar perfil", str(result))
            return
        self.status.set(f"Perfil criado: {result['path']}")
        messagebox.showinfo("Perfil criado", f"{result['path']}\nArquivos alterados: {result['count']}\n\nMantenha junto a pasta .assets para revisar ou reaplicar.")

    def _review_mod_profile(self) -> None:
        filename = filedialog.askopenfilename(
            title="Abrir perfil de mod", initialdir=str(Path(__file__).resolve().parent / "profiles"),
            filetypes=(("Perfil de mod", "*.modprofile.json"), ("JSON", "*.json")),
        )
        if not filename:
            return
        try:
            if not self.current_package:
                raise ValueError("Carregue o pacote de destino (incluindo a versão atualizada) antes de revisar.")
            profile_path = Path(filename).resolve()
            profile = mod_profile.load_profile(profile_path)
            package = self.current_package
            records = mod_profile.compare_profile(profile, package, self._workspace())
            ModProfileReview(self, profile_path, profile, records, package["sha256"] != profile["source_sha256"])
        except Exception as exc:
            messagebox.showerror("Não foi possível revisar perfil", str(exc))

    def _reapply_mod_profile(self, profile_path: Path, profile: dict, records) -> None:
        if not self.current_package:
            return
        if any(row["status"] == "ausente no pacote" for row in records):
            messagebox.showerror("Perfil incompatível", "Alguns caminhos do perfil não existem no pacote selecionado.")
            return
        changed = sum(row["status"] == "base mudou" for row in records)
        if not messagebox.askyesno(
            "Reaplicar perfil no workspace",
            f"Perfil para {profile['source_package']} ({profile['source_sha256'][:12]}…).\n"
            f"Pacote selecionado: {Path(self.current_package['path']).name} ({self.current_package['sha256'][:12]}…).\n"
            f"Arquivos cuja base mudou: {changed} de {len(records)}.\n\n"
            "As alterações serão aplicadas numa área de trabalho com backups. O .pak instalado não será alterado. Continuar?",
        ):
            return
        try:
            decoder = self._tools_script("munged_extract.py")
            package, workspace = self.current_package, self._workspace()
            self.status.set("Reaplicando perfil ao workspace...")
            self._run_background(
                lambda: mod_profile.reapply_profile(profile_path, profile, package, workspace, decoder, run_tool),
                self._profile_reapplied,
            )
        except Exception as exc:
            messagebox.showerror("Não foi possível reaplicar perfil", str(exc))

    def _profile_reapplied(self, result) -> None:
        if isinstance(result, Exception):
            self.status.set("Falha ao reaplicar perfil")
            messagebox.showerror("Falha ao reaplicar perfil", str(result))
            return
        self.status.set(f"Perfil reaplicado no workspace: {result} arquivos")
        messagebox.showinfo("Perfil reaplicado", f"{result} arquivos copiados para a área de trabalho com backups.\nValide e reconstrua um novo .pak quando estiver pronto.")

    def _rebuild_package(self) -> None:
        if not self.current_package:
            messagebox.showinfo("Nenhum pacote", "Carregue um pacote primeiro.")
            return
        try:
            packer = self._tools_script("pak_pack.py")
            decoder = self._tools_script("munged_extract.py")
            package = self.current_package
            package_root = self._workspace()
            source = Path(package["path"])
            output = filedialog.asksaveasfilename(
                title="Salvar pacote reconstruído fora da pasta do jogo",
                defaultextension=".pak",
                initialdir=str(Path(__file__).resolve().parent / "builds"),
                initialfile=f"{source.stem}-mod.pak",
                filetypes=(("Pacote PAK", "*.pak"),),
            )
            if not output:
                return
            output_path = Path(output)
            pak_probe.ensure_output_outside_game(source, output_path)
            if output_path.exists():
                raise FileExistsError(f"Não vou sobrescrever um arquivo existente: {output_path}")
            if output_path.with_suffix(output_path.suffix + ".manifest.json").exists():
                raise FileExistsError("The output manifest already exists; choose another filename.")
            self.status.set("Reconstruindo PAK a partir da área de trabalho…")

            def work():
                validation = self._validate_workspace_contents(package, package_root, decoder)
                if not validation["valid"]:
                    raise ValueError("Workspace pre-validation failed: " + " | ".join(validation["errors"]))
                run_tool([os.fspath(Path(os.sys.executable)), os.fspath(packer), os.fspath(package_root), os.fspath(output_path)])
                rebuilt = pak_probe.parse_package(output_path)
                original_paths = {entry["path"] for entry in package["entries"]}
                rebuilt_paths = {entry["path"] for entry in rebuilt["entries"]}
                if original_paths != rebuilt_paths:
                    missing = sorted(original_paths - rebuilt_paths)[:5]
                    added = sorted(rebuilt_paths - original_paths)[:5]
                    raise ValueError(f"Índice reconstruído difere do original. Faltando: {missing}; novos: {added}")
                with output_path.open("rb") as packed:
                    for entry in rebuilt["entries"]:
                        relative = entry["path"]
                        staged = validation["hashes"].get(relative)
                        if staged is None or staged["size"] != entry["payload_size"]:
                            raise ValueError(f"Missing or incorrect payload size: {relative}")
                        digest = hashlib.sha256()
                        packed.seek(entry["payload_offset"])
                        remaining = entry["payload_size"]
                        while remaining:
                            chunk = packed.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise ValueError(f"Truncated PAK payload: {relative}")
                            digest.update(chunk)
                            remaining -= len(chunk)
                        if digest.hexdigest() != staged["sha256"]:
                            raise ValueError(f"PAK payload differs from workspace: {relative}")
                manifest = {
                    "source_package": str(source),
                    "source_sha256": package["sha256"],
                    "output_package": str(output_path.resolve()),
                    "output_sha256": rebuilt["sha256"],
                    "entry_count": rebuilt["record_count"],
                    "validation": {
                        "expected_files": validation["expected_count"],
                        "changed_files": validation["changed_count"],
                        "decoded_changed_munged": validation["decoded_munged_count"],
                        "payloads_match_workspace": True,
                    },
                    "runtime_verified": False,
                }
                manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
                with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
                    json.dump(manifest, stream, indent=2)
                    stream.write("\n")
                return manifest

            self._run_background(work, self._rebuild_done)
        except Exception as exc:
            messagebox.showerror("Não foi possível reconstruir o pacote", str(exc))

    def _rebuild_done(self, result) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Falha ao reconstruir PAK", str(result))
            self.status.set("Falha ao reconstruir o pacote")
            return
        self.status.set(f"Pacote candidato criado: {result['output_package']}")
        messagebox.showinfo(
            "Pacote candidato criado",
            f"{result['output_package']}\n"
            f"Arquivos: {result['entry_count']}\nSHA-256: {result['output_sha256']}\n\n"
            "Pré-validação, índice e hashes dos payloads conferidos. Compatibilidade no jogo ainda não testada.",
        )

    def _run_background(self, operation, callback) -> None:
        def run():
            try:
                self.results.put((callback, operation(), None))
            except Exception as exc:  # surfaced in the UI thread
                self.results.put((callback, None, exc))
        threading.Thread(target=run, daemon=True).start()

    def _poll_results(self) -> None:
        try:
            while True:
                callback, value, error = self.results.get_nowait()
                callback(error if error else value)
        except queue.Empty:
            pass
        self.after(100, self._poll_results)

    def _operation_done(self, result) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Operação falhou", str(result))
            self.status.set("Operação falhou")
        else:
            self.status.set(f"Exportação concluída: {result}")
            messagebox.showinfo("Concluído", f"Arquivos extraídos para:\n{result}")

    def _replacement_done(self, result) -> None:
        if isinstance(result, Exception):
            messagebox.showerror("Substituição falhou", str(result))
            self.status.set("Substituição falhou")
        else:
            self.status.set(f"Candidato criado: {result['output_package']}")
            messagebox.showinfo(
                "Pacote candidato criado",
                f"Arquivo: {result['output_package']}\n"
                f"Tamanho esperado: {result['payload_size']} bytes\n"
                f"SHA-256 novo asset: {result['replacement_sha256']}\n\n"
                "O jogo ainda não foi usado para validar este pacote.",
            )


class ModProfileReview(tk.Toplevel):
    """Review profile hashes against the currently selected package before reapplying."""

    def __init__(self, parent, profile_path: Path, profile: dict, records: list[dict], package_updated: bool):
        super().__init__(parent)
        self.engine = parent
        self.profile_path = profile_path
        self.profile = profile
        self.records = records
        self.title(f"Revisar perfil — {profile_path.name}")
        self.geometry("980x580")
        self.minsize(760, 420)
        changed = sum(row["status"] == "base mudou" for row in records)
        missing = sum(row["status"] == "ausente no pacote" for row in records)
        source_state = "O pacote selecionado tem outro SHA-256." if package_updated else "O SHA-256 do pacote corresponde à origem."
        ttk.Label(
            self,
            text=f"Origem: {profile['source_package']}  |  {profile['source_sha256']}\n"
                 f"Pacote selecionado: {Path(parent.current_package['path']).name}  |  {parent.current_package['sha256']}\n"
                 f"{source_state} Bases alteradas: {changed}; caminhos ausentes: {missing}.",
            wraplength=930,
        ).pack(fill="x", padx=12, pady=12)
        columns = ("path", "status", "original", "current", "replacement")
        tree = ttk.Treeview(self, columns=columns, show="headings")
        for key, title, width in (
            ("path", "Caminho no pacote", 420), ("status", "Comparação", 120),
            ("original", "Hash base do perfil", 145), ("current", "Hash base atual", 145),
            ("replacement", "Hash substituto", 145),
        ):
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w" if key in ("path", "status") else "center")
        tree.pack(fill="both", expand=True, padx=12)
        for row in records:
            change = row["change"]
            tree.insert("", "end", values=(
                change["path"], row["status"], change["original_sha256"][:16],
                (row["current_sha256"] or "—")[:16], change["replacement_sha256"][:16],
            ))
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=12, pady=12)
        ttk.Button(buttons, text="Fechar", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Reaplicar no workspace...", command=self._reapply).pack(side="right", padx=8)

    def _reapply(self) -> None:
        self.engine._reapply_mod_profile(self.profile_path, self.profile, self.records)


class AnimationBrowser(tk.Toplevel):
    """Character/move browser and flipbook player for MUNGED frames."""

    def __init__(self, parent: ModEngineGUI, package: dict[str, object], workspace: Path, decoder: Path):
        super().__init__(parent)
        self.title(f"Animações — {Path(package['path']).name}")
        self.geometry("1120x760")
        self.minsize(900, 600)
        self.package = package
        self.engine = parent
        self.workspace = workspace
        self.decoder = decoder
        self.results: queue.Queue = queue.Queue()
        self.images: dict[str, Path] = {}
        self.records: dict[str, dict[str, list[dict[str, object]]]] = {}
        self.modified_paths: set[str] = set()
        self.playing = False
        self.closed = False
        self.load_generation = 0
        self.play_after_id = None
        self.photo = None
        self.character = tk.StringVar()
        self.motion = tk.StringVar()
        self.fps = tk.StringVar(value="12")
        self.status = tk.StringVar(value="Escolha um personagem e um movimento.")
        self.frame_label = tk.StringVar(value="—")
        changes_path = workspace.parent / ".mod_engine_changes.json"
        if changes_path.is_file():
            try:
                self.modified_paths = {item["path"] for item in json.loads(changes_path.read_text(encoding="utf-8")).get("changes", [])}
            except (OSError, ValueError, KeyError, TypeError):
                self.modified_paths = set()

        for entry in package["entries"]:
            info = self._classify(entry)
            if info is None:
                continue
            character, motion, frame = info
            self.records.setdefault(character, {}).setdefault(motion, []).append({**entry, "frame_name": frame})
        for motions in self.records.values():
            for frames in motions.values():
                frames.sort(key=lambda item: self._natural_key(str(item["frame_name"])))

        self._build()
        self.character_box["values"] = sorted(self.records, key=self._natural_key)
        if self.character_box["values"]:
            self.character_box.current(0)
            self._character_changed()
        else:
            self.status.set("Este pacote não contém frames de personagem reconhecidos.")
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    @staticmethod
    def _classify(entry):
        path = str(entry["path"])
        if not path.lower().endswith(".munged"):
            return None
        parts = PurePosixPath(path).stem.split("~")
        if len(parts) < 4 or parts[0].casefold() != "sprites":
            return None
        marker = next((i for i in range(2, len(parts)) if "frames" in parts[i].casefold()), None)
        if marker is None or marker == len(parts) - 1:
            return None
        frame_name = "~".join(parts[marker + 1:])
        if frame_name.casefold().endswith("_mask"):
            return None
        return parts[1], " / ".join(parts[2:marker + 1]), frame_name

    @staticmethod
    def _natural_key(value: str):
        return [int(piece) if piece.isdigit() else piece.casefold() for piece in re.split(r"(\d+)", value)]

    def _build(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Personagem:").pack(side="left")
        self.character_box = ttk.Combobox(top, textvariable=self.character, state="readonly", width=22)
        self.character_box.pack(side="left", padx=(6, 18))
        self.character_box.bind("<<ComboboxSelected>>", lambda _event: self._character_changed())
        ttk.Label(top, text="Movimento:").pack(side="left")
        self.motion_box = ttk.Combobox(top, textvariable=self.motion, state="readonly", width=50)
        self.motion_box.pack(side="left", padx=6, fill="x", expand=True)
        self.motion_box.bind("<<ComboboxSelected>>", lambda _event: self._motion_changed())

        body = ttk.Frame(self, padding=(10, 0, 10, 8))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, width=290)
        left.pack(side="left", fill="y", padx=(0, 10))
        ttk.Label(left, text="Frames em ordem natural (Ctrl/Shift para selecionar)").pack(anchor="w")
        self.frame_tree = ttk.Treeview(left, columns=("frame", "status"), show="headings", height=25, selectmode="extended")
        self.frame_tree.heading("frame", text="Frame")
        self.frame_tree.heading("status", text="Estado")
        self.frame_tree.column("frame", width=280, anchor="w")
        self.frame_tree.column("status", width=86, anchor="center")
        self.frame_tree.tag_configure("modified", foreground="#a13c00")
        self.frame_tree.pack(fill="both", expand=True, pady=(5, 0))
        self.frame_tree.bind("<<TreeviewSelect>>", lambda _event: self._show_selected())

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(right, background="#262626", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        playback = ttk.Frame(right, padding=(0, 8, 0, 0))
        playback.pack(fill="x")
        ttk.Button(playback, text="|◀", width=5, command=lambda: self._step(0)).pack(side="left", padx=(0, 5))
        ttk.Button(playback, text="◀", width=5, command=self._previous).pack(side="left", padx=(0, 5))
        self.play_button = ttk.Button(playback, text="▶ Reproduzir", command=self._toggle_play)
        self.play_button.pack(side="left", padx=(0, 5))
        ttk.Button(playback, text="▶|", width=5, command=self._next).pack(side="left", padx=(0, 12))
        ttk.Label(playback, text="FPS:").pack(side="left")
        ttk.Spinbox(playback, from_=1, to=60, textvariable=self.fps, width=5).pack(side="left", padx=5)
        ttk.Label(playback, textvariable=self.frame_label).pack(side="right")
        ttk.Button(playback, text="Aplicar substitutos selecionados…", command=self._apply_replacements).pack(side="right", padx=(8, 0))
        ttk.Label(self, textvariable=self.status, padding=(10, 0, 10, 8)).pack(fill="x", anchor="w")

    def _apply_replacements(self) -> None:
        selections = self.frame_tree.selection()
        if not selections:
            messagebox.showinfo("Selecione frames", "Selecione um ou mais frames na lista.", parent=self)
            return
        items = self.records.get(self.character.get(), {}).get(self.motion.get(), [])
        selected = [items[int(iid)] for iid in selections]
        folder = filedialog.askdirectory(parent=self, title="Pasta com os arquivos .munged substitutos")
        if not folder:
            return
        self.status.set(f"Validando {len(selected)} arquivos substitutos…")
        self.engine._stage_munged_batch(self.package, self.workspace, selected, Path(folder), self._batch_done)

    def _batch_done(self, result) -> None:
        if isinstance(result, Exception):
            self.status.set(f"Lote não aplicado: {result}")
            messagebox.showerror("Lote não aplicado", str(result), parent=self)
            return
        self.modified_paths.update(result["paths"])
        self.status.set(f"Aplicadas {result['count']} alterações; relendo a animação para mostrar o resultado…")
        self._motion_changed()

    def _character_changed(self) -> None:
        self._stop_playback()
        motions = sorted(self.records.get(self.character.get(), {}), key=self._natural_key)
        self.motion_box["values"] = motions
        if motions:
            self.motion_box.current(0)
            self._motion_changed()

    def _motion_changed(self) -> None:
        self._stop_playback()
        self.load_generation += 1
        generation = self.load_generation
        self.frame_tree.delete(*self.frame_tree.get_children())
        self.canvas.delete("all")
        self.photo = None
        self.images.clear()
        items = self.records.get(self.character.get(), {}).get(self.motion.get(), [])
        for number, item in enumerate(items):
            changed = str(item["path"]) in self.modified_paths
            self.frame_tree.insert(
                "", "end", iid=str(number),
                values=(item["frame_name"], "Modificado" if changed else ""),
                tags=("modified",) if changed else (),
            )
        self.frame_label.set(f"0 / {len(items)}")
        if not items:
            self.status.set("Nenhum frame neste movimento.")
            return
        self.status.set(f"Decodificando {len(items)} frames de {self.character.get()} / {self.motion.get()}…")

        def decode_motion():
            preview_root = self.workspace.parent / ".mod_engine_previews"
            preview_root.mkdir(exist_ok=True)
            run_dir = Path(tempfile.mkdtemp(prefix="animation_", dir=preview_root))
            input_dir = run_dir / "input"
            output_dir = run_dir / "output"
            input_dir.mkdir()
            output_dir.mkdir()
            selected_items = list(items)
            for item in selected_items:
                source = self.workspace.joinpath(*PurePosixPath(str(item["path"])).parts)
                if not source.is_file():
                    raise FileNotFoundError(f"Frame ausente da área de trabalho: {source}")
                shutil.copy2(source, input_dir / source.name)
            palette_root = self.workspace / "srcdata" / "munged" / "scripts"
            if not palette_root.is_dir() or not any(palette_root.rglob("*.sprbin")):
                raise FileNotFoundError("Não encontrei .sprbin em srcdata/munged/scripts para as paletas deste pacote.")
            run_tool(
                [
                    os.fspath(Path(os.sys.executable)), os.fspath(self.decoder),
                    os.fspath(input_dir), os.fspath(output_dir), "--auto-palette",
                    "--palette-root", os.fspath(palette_root),
                ]
            )
            decoded = {}
            pngs = list(output_dir.rglob("*.png"))
            for item in selected_items:
                stem = PurePosixPath(str(item["path"])).stem.casefold()
                image = next((p for p in pngs if p.stem.casefold() == stem), None)
                if image is None:
                    raise RuntimeError(f"O decodificador não gerou a prévia para {item['frame_name']}.")
                decoded[str(item["path"])] = image
            return decoded

        threading.Thread(target=self._decode_worker, args=(generation, decode_motion), daemon=True).start()

    def _decode_worker(self, generation, operation) -> None:
        try:
            self.results.put((generation, operation(), None))
        except Exception as exc:
            self.results.put((generation, None, exc))

    def _poll(self) -> None:
        if self.closed:
            return
        try:
            while True:
                generation, decoded, error = self.results.get_nowait()
                if generation != self.load_generation:
                    continue
                if error:
                    self.status.set(f"Falha ao decodificar: {error}")
                    messagebox.showerror("Falha ao decodificar movimento", str(error), parent=self)
                    continue
                self.images = decoded
                self.status.set(f"Pronto: {len(decoded)} frames decodificados.")
                children = self.frame_tree.get_children()
                if children:
                    self.frame_tree.selection_set(children[0])
                    self.frame_tree.focus(children[0])
                    self._show_selected()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _show_selected(self) -> None:
        selection = self.frame_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        items = self.records.get(self.character.get(), {}).get(self.motion.get(), [])
        if index >= len(items):
            return
        item = items[index]
        image_path = self.images.get(str(item["path"]))
        self.frame_label.set(f"{index + 1} / {len(items)}   {item['frame_name']}")
        if image_path is None:
            return
        try:
            image = tk.PhotoImage(file=os.fspath(image_path))
            width = max(1, self.canvas.winfo_width() - 24)
            height = max(1, self.canvas.winfo_height() - 24)
            scale = max(1, (image.width() + width - 1) // width, (image.height() + height - 1) // height)
            if scale > 1:
                image = image.subsample(scale, scale)
            self.photo = image
            self.canvas.delete("all")
            self.canvas.create_image(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, image=image, anchor="center")
        except Exception as exc:
            self.status.set(f"Falha ao exibir frame: {exc}")

    def _select_index(self, index: int) -> None:
        children = self.frame_tree.get_children()
        if not children:
            return
        index %= len(children)
        self.frame_tree.selection_set(children[index])
        self.frame_tree.focus(children[index])
        self.frame_tree.see(children[index])
        self._show_selected()

    def _current_index(self) -> int:
        selected = self.frame_tree.selection()
        return int(selected[0]) if selected else 0

    def _previous(self) -> None:
        self._select_index(self._current_index() - 1)

    def _next(self) -> None:
        self._select_index(self._current_index() + 1)

    def _step(self, index: int) -> None:
        self._select_index(index)

    def _toggle_play(self) -> None:
        if self.playing:
            self._stop_playback()
            return
        if not self.frame_tree.get_children():
            return
        if not self.images:
            self.status.set("Aguarde a decodificação dos frames.")
            return
        self.playing = True
        self.play_button.configure(text="❚❚ Pausar")
        self._tick()

    def _tick(self) -> None:
        if not self.playing:
            return
        try:
            fps = max(1, min(60, int(self.fps.get())))
        except ValueError:
            fps = 12
        self._next()
        self.play_after_id = self.after(max(1, 1000 // fps), self._tick)

    def _stop_playback(self) -> None:
        self.playing = False
        self.play_button.configure(text="▶ Reproduzir")
        if self.play_after_id is not None:
            try:
                self.after_cancel(self.play_after_id)
            except tk.TclError:
                pass
            self.play_after_id = None

    def _close(self) -> None:
        self.closed = True
        self._stop_playback()
        self.destroy()


if __name__ == "__main__":
    ModEngineGUI().mainloop()
