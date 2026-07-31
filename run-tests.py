#!/usr/bin/env python3
"""
run-tests.py — Script d'exécution des tests unifié (P6 exercice 2, étape 1).

Détecte automatiquement le type de projet (Angular ou Spring Boot) présent
dans le répertoire courant, exécute sa suite de tests, puis rassemble les
rapports JUnit XML produits dans un dossier `test-results/` normalisé.

Aucune dépendance externe : uniquement la bibliothèque standard Python.
Conçu pour tourner à l'identique en local (WSL) et sur un runner CI Ubuntu.
"""

import shutil
import subprocess
import sys
from pathlib import Path

# --- Configuration ----------------------------------------------------------

# Racine du repo = dossier où se trouve ce script (déposé à la racine de chaque
# projet). Tous les chemins sont résolus par rapport à cette racine.
PROJECT_ROOT = Path(__file__).resolve().parent

# Dossier de sortie normalisé, commun aux deux types de projet (critère fiche).
RESULTS_DIR = PROJECT_ROOT / "test-results"

# Pour chaque type de projet : comment le reconnaître, ses dépendances requises,
# comment le tester, et où l'outil dépose NATIVEMENT ses rapports JUnit XML.
PROJECT_TYPES = {
    "angular": {
        "marker": "angular.json",                 # fichier signature du projet
        "dependency_dir": "node_modules",          # deps à vérifier avant test
        "test_command": ["npm", "test"],           # déjà headless+no-sandbox (karma.conf.js)
        "reports_glob": "reports/*.xml",           # sortie native karma-junit-reporter
    },
    "java": {
        "marker": "gradlew",
        "dependency_dir": None,                     # Gradle gère ses propres deps
        "test_command": ["./gradlew", "test"],
        "reports_glob": "build/test-results/test/TEST-*.xml",  # sortie native Gradle
    },
}


# --- Étapes (une responsabilité par fonction) -------------------------------

def detect_project_type():
    """Repère le type de projet d'après un fichier marqueur présent à la racine.

    Retourne 'angular' ou 'java'. Si aucun marqueur n'est trouvé, on s'arrête
    avec une erreur explicite plutôt que de deviner : le script a peut-être été
    lancé au mauvais endroit.
    """
    for name, config in PROJECT_TYPES.items():
        if (PROJECT_ROOT / config["marker"]).exists():
            print(f"[detect] Projet détecté : {name} (marqueur : {config['marker']})")
            return name
    sys.exit(
        f"[detect] ERREUR : aucun projet reconnu dans {PROJECT_ROOT}. "
        "Marqueurs attendus : "
        + ", ".join(c["marker"] for c in PROJECT_TYPES.values())
    )


def check_dependencies(config):
    """Vérifie la présence des dépendances avant de tester (critère fiche).

    Le script VÉRIFIE mais n'INSTALLE pas : l'installation et sa mise en cache
    relèvent du pipeline CI (critère distinct de l'étape 2). Pour Java,
    `dependency_dir` vaut None car Gradle télécharge ses deps tout seul.
    """
    dep_dir = config["dependency_dir"]
    if dep_dir is None:
        return
    if not (PROJECT_ROOT / dep_dir).is_dir():
        sys.exit(
            f"[deps] ERREUR : dépendances absentes ('{dep_dir}/' introuvable). "
            "Installe-les avant de tester (`npm ci` en local, ou l'étape "
            "d'installation du pipeline en CI)."
        )
    print(f"[deps] Dépendances présentes ('{dep_dir}/').")


def clean_results():
    """Vide test-results/ avant chaque exécution (critère fiche : nettoyage).

    On repart d'un dossier propre pour qu'un vieux rapport ne fausse pas
    l'interprétation d'un run ultérieur. On ne touche QU'À test-results/
    (notre périmètre), jamais aux dossiers natifs des outils (reports/, build/).
    """
    if RESULTS_DIR.exists():
        shutil.rmtree(RESULTS_DIR)
    RESULTS_DIR.mkdir(parents=True)
    print(f"[clean] Dossier propre : test-results/")


def run_tests(config):
    """Lance la suite de tests et renvoie son code de sortie.

    `check=False` est volontaire : un échec de test n'est pas une exception à
    lever, c'est une issue légitime dont on veut propager le code de sortie
    tel quel (voir main).
    """
    command = config["test_command"]
    print(f"[test] Exécution : {' '.join(command)}")
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    print(f"[test] Terminé (code de sortie : {result.returncode}).")
    return result.returncode


def collect_reports(config):
    """Copie les rapports JUnit XML natifs vers test-results/.

    Chaque outil écrit ailleurs (reports/ pour Karma, build/test-results/test/
    pour Gradle) : on rassemble tout dans test-results/ SANS toucher aux configs
    des projets. La normalisation est la seule responsabilité de ce script.
    Retourne le nombre de fichiers copiés.
    """
    xml_files = list(PROJECT_ROOT.glob(config["reports_glob"]))
    for xml in xml_files:
        shutil.copy2(xml, RESULTS_DIR / xml.name)
        print(f"[collect] {xml.relative_to(PROJECT_ROOT)} -> test-results/{xml.name}")
    print(f"[collect] {len(xml_files)} rapport(s) copié(s).")
    return len(xml_files)


# --- Orchestration ----------------------------------------------------------

def main():
    """Enchaîne les étapes et détermine le code de sortie final.

    Codes de sortie :
      0   = tests réussis ET rapports collectés
      !=0 = tests échoués (code propagé), ou anomalie (deps/rapports manquants)
    """
    project_type = detect_project_type()
    config = PROJECT_TYPES[project_type]

    check_dependencies(config)
    clean_results()
    test_exit_code = run_tests(config)
    reports_count = collect_reports(config)

    # Cas anormal : tests OK mais aucun rapport trouvé -> le job du script n'est
    # pas rempli, on signale un échec (config de reporter probablement cassée).
    if test_exit_code == 0 and reports_count == 0:
        sys.exit(
            "[main] ERREUR : tests réussis mais aucun rapport JUnit XML trouvé "
            f"(motif : {config['reports_glob']})."
        )

    # Sinon on propage le code de sortie des tests : la CI verra vert ou rouge.
    sys.exit(test_exit_code)


if __name__ == "__main__":
    main()