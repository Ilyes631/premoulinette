# Guide débutant : utiliser PréMoulinette sur ton PC

Ce guide est fait pour quelqu'un qui **ne connaît pas l'informatique**.
Suis les étapes dans l'ordre. L'installation se fait **une seule fois**.

> **C'est quoi PréMoulinette ?** Un outil qui vérifie ton TP de programmation (Python) **avant** que tu le
> rendes. Tu lui donnes le **sujet** (la consigne) et ton **travail**, et il te dit ce qui ne respecte pas
> le sujet : fichier mal placé, faute de frappe dans un texte, mauvais résultat… Il ne te donne **pas** ta
> note : c'est une vérification avant le vrai rendu. Tout reste sur ton ordinateur.

---

## Partie 1 : Installer (une seule fois)

### 1. Installer les 3 logiciels nécessaires

Télécharge et installe ces logiciels. Garde les options par défaut, en cliquant « Suivant » jusqu'au bout.

| Logiciel | Où le trouver | Attention |
|---|---|---|
| **Python** | https://www.python.org/downloads/ → bouton jaune « Download Python » | Sur le premier écran de l'installation, **coche la case « Add python.exe to PATH »** en bas, puis « Install Now ». |
| **Node.js** | https://nodejs.org → bouton **« LTS »** | Rien de spécial. |
| **Docker Desktop** *(recommandé)* | https://www.docker.com/products/docker-desktop/ | Au premier lancement, accepte la licence (gratuite pour un usage perso ou étudiant). Tu peux cliquer « Skip » pour ne pas créer de compte. Un redémarrage du PC peut être demandé. |

> **Docker, c'est quoi ?** Une « boîte fermée » dans laquelle PréMoulinette fait tourner ton code, pour
> qu'il ne puisse rien abîmer sur ton PC. Sans Docker, ça marche aussi : voir la [Partie 4](#partie-4--sans-docker).

### 2. Télécharger PréMoulinette

1. Va sur **https://github.com/Ilyes631/premoulinette**
2. Clique sur le bouton vert **« Code »**, puis sur **« Download ZIP »**.
3. Ouvre ton dossier **Téléchargements**, fais un **clic droit** sur `premoulinette-main.zip`, puis **« Extraire tout… »**.
4. Déplace le dossier extrait où tu veux, par exemple sur ton **Bureau**.

### 3. Premier lancement (installation automatique)

1. Ouvre le dossier `premoulinette-main`.
2. **Double-clique sur `start.bat`**.
   - Si Windows affiche *« Windows a protégé votre ordinateur »*, clique **« Informations complémentaires »**, puis **« Exécuter quand même »**.
3. Une fenêtre noire s'ouvre et installe tout ce qu'il faut. **Ça prend environ 5 minutes, une seule fois.**
4. Quand c'est fini, ton navigateur s'ouvre tout seul sur **http://localhost:5173**. C'est PréMoulinette.

---

## Partie 2 : Vérifier ton TP (à chaque fois)

### Étape 1 : lancer PréMoulinette
Double-clique sur **`start.bat`** et attends 10 secondes.
**Ne ferme pas la fenêtre noire** tant que tu utilises PréMoulinette : c'est le moteur.
Si tu utilises Docker, attends qu'il affiche **« Engine running »**.

### Étape 2 : récupérer le sujet du TP
1. Ouvre la page du sujet de ton TP (sur l'intranet de ton école).
2. Appuie sur **Ctrl + S**.
3. En bas de la fenêtre, choisis le type **« Page Web, HTML uniquement »**, puis enregistre dans **Téléchargements**.
   *Si ton sujet est un PDF, télécharge simplement le PDF.*

### Étape 3 : donner le sujet à PréMoulinette
Fais **glisser** le fichier du sujet dans la case de gauche, **« Subject »**.
Clique ensuite sur **« Review extracted requirements »** pour vérifier que PréMoulinette a bien compris
le sujet : fichiers, fonctions, exemples. Si quelque chose est faux, corrige-le avec **« Edit »**.

### Étape 4 : donner ton travail
Dans la case de droite, **« Student project »**, onglet **« Local folder »** :
1. Ouvre le dossier de ton TP dans l'Explorateur Windows. Prends le dossier principal de ton dépôt, celui que tu as cloné.
2. Clique dans la **barre d'adresse** en haut de la fenêtre. Le chemin s'affiche, par exemple `C:\Users\toi\Documents\mon-tp`.
   Fais **Ctrl + C**.
3. Dans PréMoulinette, clique dans la case du chemin, fais **Ctrl + V**, puis **« Use folder »**.

> **Ton travail est dans Ubuntu (WSL) ?** Dans ton terminal Ubuntu, va dans le dossier de ton TP
> (`cd …`), puis tape `explorer.exe .` (avec le point). Une fenêtre Windows s'ouvre sur ce dossier :
> copie l'adresse en haut (elle commence par `\\wsl.localhost\…`) et colle-la dans PréMoulinette.

### Étape 5 : lancer l'analyse
Clique sur **« Analyze project »** et attends, environ 30 secondes avec Docker.

- **DO NOT SUBMIT YET** : il reste des erreurs à corriger.
- **READY TO SUBMIT** : tout ce qui peut être vérifié à partir du sujet est bon.
  *(L'école peut avoir des tests cachés : ce n'est pas une garantie de note.)*

### Étape 6 : comprendre et corriger les erreurs
1. Clique sur l'onglet **« Issues »** : la liste des erreurs, rangées par fichier.
2. Clique sur une erreur :
   - **Expected** = ce que le sujet demande,
   - **Received** = ce que ton programme fait vraiment.
3. **« Explain »** : explication simple en français.
   **« How to fix »** : la petite modification à faire (rien n'est modifié automatiquement).
4. Corrige ton code comme d'habitude.
5. Reviens sur PréMoulinette et clique **« Re-analyze »**.
6. Recommence jusqu'à **READY TO SUBMIT**.

> Astuce : corrige d'abord les erreurs marquées **Critical**.

### Étape 7 : rendre ton travail (le vrai rendu, toi-même)
PréMoulinette ne rend **jamais** ton travail à ta place. Quand tout est bon, fais ton rendu comme
d'habitude (`git add`, `git commit`, `git push`, puis le tag demandé par le sujet).

### Arrêter PréMoulinette
Ferme la fenêtre noire. Tu peux aussi quitter Docker Desktop.

---

## Partie 3 : En cas de problème

| Problème | Solution |
|---|---|
| `start.bat` dit que **Node.js n'est pas installé** | Installe Node.js (Partie 1), puis relance `start.bat`. |
| L'installation échoue en parlant de **Python** | Réinstalle Python en **cochant « Add python.exe to PATH »**, puis relance `start.bat`. |
| Le navigateur affiche **« Impossible de se connecter »** | Attends 10 secondes de plus, puis recharge la page (**F5**). |
| Message **« Docker is not available »** | Ouvre Docker Desktop et attends « Engine running », ou utilise la [Partie 4](#partie-4--sans-docker). |
| Une erreur te paraît fausse | Vérifie dans **« Review extracted requirements »** que le sujet a bien été compris, et corrige avec « Edit ». |
| Je veux tout réinstaller | Supprime les dossiers `backend\.venv` et `frontend\node_modules`, puis relance `start.bat`. |

---

## Partie 4 : Sans Docker

1. Dans PréMoulinette, clique sur **Settings** (en haut).
2. Dans **Sandbox**, coche **« I understand the risks and allow Developer mode on this machine »**.
3. Clique **Save settings**.

Ton code tournera alors directement sur ton PC, avec des protections plus légères. C'est suffisant pour
vérifier **ton propre** travail, mais n'analyse pas le code de quelqu'un en qui tu n'as pas confiance.

---

## Partie 5 (optionnel) : explications par IA

PréMoulinette marche **sans IA** : les explications intégrées suffisent. Si tu veux en plus des
explications rédigées par Claude :

1. Crée un compte sur **https://console.anthropic.com**.
2. Dans **Billing**, ajoute un peu de crédit (c'est payant à l'usage : quelques centimes par explication).
3. Dans **API Keys**, clique **Create Key** et copie la clé (elle commence par `sk-ant-…`).
4. Dans PréMoulinette, va dans **Settings**, partie **AI explanations** : active l'IA, colle ta clé, coche ce que tu acceptes d'envoyer, puis **Save**.

Ta clé reste sur ton ordinateur. Seul le petit morceau de code concerné par l'erreur est envoyé, jamais tout ton projet.

---

## Mac ou Linux ?
Même chose, mais à la place de `start.bat`, ouvre un terminal dans le dossier et tape `./start.sh`.
