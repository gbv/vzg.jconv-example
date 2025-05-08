# Beispiel-Notebooks für eine Konvertierung in das VZG JSON Austauschformat

- [example.ipynb](example.ipynb) Konvertierung in das Austauschformat
- [oai-request.ipynb](oai-request.ipynb) OAI Abruf absetzen und apspeichern

## Lokale Installation

Das Beispiel liegt in Form eines [Jupyter](https://jupyter.org "Jupyter Homepage") Notebooks vor.
Falls man das Notebook selbst ausführen möchte, benötigt man z.B. eine lokale Jupyter Instanz.
Diese lässt sich recht simpel mithilfe einer virtuellen Python Umgebung erstellen.

Der Python-Interpreter muss mindestens in der Version 3.12 oder höher vorliegen.

### Jupyter Installation auf einem Linux-System, z.B. Ubuntu

Welche Python Version ist installiert?

```bash
python3 --version
```

Erzeugen einer virtuellen Python Umgebung im Heimat-Verzeichnis

```bash
cd $HOME
python3 -m venv jupyter
```

Vor jedem benutzen der virtuellen Umgebung muss diese einmal pro Sitzung aktiviert werden.

```bash
cd $HOME/jupyter
source bin/activate
```

Jupyter innerhalb der virtuellen Umgebung installieren

```bash
pip install jupyterlab
```

Danach am besten einen eigenen Bereich für die Notebooks anlegen

```bash
mkdir $HOME/jupyter/notebooks
```

### vzg.jconv Modul installieren

```bash
cd $HOME/jupyter
pip install vzg.jconv
```

### Beispiel Notebook installieren

```bash
cd $HOME/jupyter/notebooks
git clone https://github.com/gbv/vzg.jconv-example.git
```

### Jupyter starten und das Notebook benutzen

```bash
cd $HOME/jupyter/notebooks/vzg.jconv-example
jupyter lab
```

Dieser Aufruf wird das Notebook im Browser öffnen.
