#!/usr/bin/env bash
# Общая выкладка Python-игры на GitHub. Зовётся из tools/publish_github.sh каждой игры
# (тонкая обёртка), настройки игры - в её tools/publish.conf.
#
#   bash <игра>/tools/publish_github.sh            # только код
#   bash <игра>/tools/publish_github.sh v1.0.0     # код и тег
#   DRY_RUN=1 bash <игра>/tools/publish_github.sh  # собрать и проверить, ничего не отправлять
#   (напрямую: bash PythonAiGames/tools/publish_game.sh <папка игры> [vX.Y.Z])
#
# Источник правды - Gitea. На GitHub уезжает копия main (ветка github-main, пересобирается
# каждый раз заново - отсюда --force), в которой по всей истории заменено личное:
#   почта автора (git config user.email)  -> анонимная почта GitHub (авторы, сообщения, файлы);
#   адрес домашнего Gitea (из origin)     -> gitea.local;
#   папка над игрой (C:/.../AiGames/)     -> убирается вместе с разделителем, как раньше;
#   папка Drive на ПК в любом написании   -> C:\Work (C:\ C:/ /c/ C:\\ C--Drive- и регистр);
#   имя автора (git config publish.privateName и publish.privateExtra, через |; в имени с
#     пробелом отдельно и фамилия)        -> «автор» в том же падеже / «the author».
# Ни одна из этих строк здесь не записана: они берутся из настроек git и места игры.
# После чистки всё проверяется ещё раз, и если что-то осталось - пуш отменяется.
#
# tools/publish.conf игры (bash, читается через source):
#   REPO=ALEXalesha/<имя>         обязательно (его же читает InstallAll/tools/release.ps1);
#   DROP_PATHS=(docs/spec.md)     пути, вырезаемые из всей публикуемой истории;
#   TEXT_FORBID='слово|слово2'    ERE без учёта регистра: в файлах и сообщениях - пуш отменён;
#   TEXT_SED=('s#a#b#g')          sed -E правила поверх личного (файлы TEXT_GREP и сообщения);
#   TEXT_GREP='ERE'               какие файлы переписывать правилами TEXT_SED.
#
# Проверки - без конвейеров: `git log | grep -q` и `git grep | head` при pipefail получали
# SIGPIPE (141) на длинной истории, и проверка молча проходила. Здесь каждая команда пишет
# в файл, код 0 - нашлось, 1 - нет, любой другой - скрипт останавливается.
# Сообщения коммитов при отказе не печатаются (там само личное).
# Тесты: bash PythonAiGames/tests/test_publish_game.sh (и --mutants).
set -euo pipefail

export PATH="$PATH:/c/Program Files/GitHub CLI"
PUBLIC_EMAIL=203467574+ALEXalesha@users.noreply.github.com
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRUB="$HERE/publish_game_scrub.pl"
GAME="${1:?usage: publish_game.sh <папка игры> [vX.Y.Z]}"
TAG="${2:-}"
BR=github-main

cd "$GAME"
CONF=tools/publish.conf
[ -f "$CONF" ] || { echo "нет $CONF" >&2; exit 1; }
REPO=""; DROP_PATHS=(); TEXT_FORBID=""; TEXT_SED=(); TEXT_GREP=""
# shellcheck source=/dev/null
. "$CONF"
[ -n "$REPO" ] || { echo "в $CONF нет REPO=" >&2; exit 1; }

PRIVATE_EMAIL="$(git config user.email || true)"
LAN_GITEA="$(git remote get-url origin 2>/dev/null | sed -E 's#^[a-z]+://([^/]+)/.*#\1#' || true)"
NAMES="$(git config --get publish.privateName || true)"
EXTRA="$(git config --get publish.privateExtra || true)"
[ -n "$PRIVATE_EMAIL" ] || { echo "в git config нет user.email - не с чем сверять" >&2; exit 1; }
[ -n "$LAN_GITEA" ] || { echo "нет адреса origin" >&2; exit 1; }
[ -n "$NAMES" ] || { echo "нет git config publish.privateName - имя автора не заменить (как в Paint, или через release.ps1)" >&2; exit 1; }
# filter-branch с изменениями в рабочей копии отказывается молча - лучше сказать сразу
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "в рабочей копии незакоммиченные изменения - сначала коммит" >&2
  exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT                       # только свои временные файлы

# --- личные строки -----------------------------------------------------------------------
# Для perl (замена) - через окружение; для проверок - список строк в файле (grep -F -f).
export PG_EMAIL="$PRIVATE_EMAIL" PG_PUBLIC_EMAIL="$PUBLIC_EMAIL"
export PG_GITEA="$LAN_GITEA" PG_GITEA_HOST="${LAN_GITEA%%:*}"
# PUBLISH_PARENT - для пробного прогона из временного клона: папка, где игра лежит на самом деле
export PG_DIR; PG_DIR="${PUBLISH_PARENT:-$(cd .. && (pwd -W 2>/dev/null || pwd))}"   # C:/.../AiGames
export PG_DIR_BS="${PG_DIR//\//\\}"
export PRIVATE_NAME="$NAMES|$EXTRA"
# Папка Drive на ПК: только шаблон с первым именем (без фамилии); имя склеено из кусков,
# чтобы строки пути не было ни в одном файле.
PN=Ale; PN="${PN}xey"; export PG_PATH_NAME="$PN"
PATH_RE='drive([\\/]+|-+)'"$PN"

GREPFILE="$WORK/private.txt"; : > "$GREPFILE"
FULL_NAMES=()
add() { [ ${#1} -ge 4 ] && printf '%s\n' "$1" >> "$GREPFILE"; return 0; }
add "$PRIVATE_EMAIL"; add "$PG_GITEA_HOST"; add "$PG_DIR"; add "$PG_DIR_BS"
IFS='|' read -r -a ITEMS <<< "$PRIVATE_NAME"
for n in "${ITEMS[@]}"; do
  n="$(printf '%s' "$n" | sed 's/^ *//; s/ *$//')"
  [ -n "$n" ] || continue
  add "$n"
  case "$n" in *" "*) add "${n##* }"; FULL_NAMES+=("$n") ;; esac
done

# TEXT_SED: правила игры, после личного - и в сообщениях, и в файлах
TEXTSED="$WORK/text.sed"; : > "$TEXTSED"
for r in "${TEXT_SED[@]:-}"; do [ -n "$r" ] && printf '%s\n' "$r" >> "$TEXTSED"; done
CLEAN="perl -p '$SCRUB' | sed -E -f '$TEXTSED'"

# --- что переписывать в файлах ---------------------------------------------------------
# rev_grep <файл ревизий> <опции git grep...>: git grep по всем коммитам кусками по 200
# (в одну командную строку Windows тысячи SHA не влезают; PG_CHUNK - размер куска для тестов). Вывод - в $WORK/hit.txt.
# 0 - нашлось, 1 - нет; любой другой код - стоп (сломанный шаблон не должен проходить молча).
rev_grep() {
  local revs="$1" rc found=1 part
  shift
  : > "$WORK/hit.txt"
  rm -f "$WORK"/revpart.*
  split -l "${PG_CHUNK:-200}" "$revs" "$WORK/revpart."
  for part in "$WORK"/revpart.*; do
    [ -s "$part" ] || continue
    mapfile -t CH < "$part"
    rc=0
    git grep "$@" "${CH[@]}" -- >> "$WORK/hit.txt" 2> "$WORK/hit.err" || rc=$?
    case $rc in
      0) found=0 ;;
      1) ;;
      *) echo "проверка сломалась (код $rc): git grep $1 ..." >&2; head -5 "$WORK/hit.err" >&2; exit 1 ;;
    esac
  done
  return $found
}
# hit <команда...>: то же для одной команды
hit() {
  local rc=0
  "$@" > "$WORK/hit.txt" 2> "$WORK/hit.err" || rc=$?
  case $rc in
    0) return 0 ;;
    1) return 1 ;;
    *) echo "проверка сломалась (код $rc): $1 $2 ..." >&2; head -5 "$WORK/hit.err" >&2; exit 1 ;;
  esac
}
# cancel <причина> [show]: show - первые 5 совпадений (имена файлов, строки TEXT_FORBID)
cancel() {
  echo "$1 - пуш отменён" >&2
  if [ "${2:-}" = show ]; then head -5 "$WORK/hit.txt" | cut -c1-200 >&2; fi
  exit 1
}

git rev-list main > "$WORK/src-revs.txt"
: > "$WORK/dirty.txt"
if rev_grep "$WORK/src-revs.txt" -I -l -i -F -f "$GREPFILE"; then cat "$WORK/hit.txt" >> "$WORK/dirty.txt"; fi
if rev_grep "$WORK/src-revs.txt" -I -l -i -E "$PATH_RE"; then cat "$WORK/hit.txt" >> "$WORK/dirty.txt"; fi # scrub:path
if [ -n "$TEXT_GREP" ] && rev_grep "$WORK/src-revs.txt" -I -l -E "$TEXT_GREP"; then cat "$WORK/hit.txt" >> "$WORK/dirty.txt"; fi
sed -i 's/^[^:]*://' "$WORK/dirty.txt"
sort -u -o "$WORK/dirty.txt" "$WORK/dirty.txt"
if [ -s "$WORK/dirty.txt" ]; then
  echo "личное в файлах ($(wc -l < "$WORK/dirty.txt")): $(tr '\n' ' ' < "$WORK/dirty.txt")- переписываю содержимое"
fi

# --- 1. ветка github-main: авторы, сообщения, файлы, DROP_PATHS - за один проход ---------
ENVF="
  if [ \"\$GIT_AUTHOR_EMAIL\" = '$PRIVATE_EMAIL' ]; then export GIT_AUTHOR_EMAIL='$PUBLIC_EMAIL'; fi
  if [ \"\$GIT_COMMITTER_EMAIL\" = '$PRIVATE_EMAIL' ]; then export GIT_COMMITTER_EMAIL='$PUBLIC_EMAIL'; fi"
for n in "${FULL_NAMES[@]:-}"; do
  [ -n "$n" ] || continue
  ENVF="$ENVF
  if [ \"\$GIT_AUTHOR_NAME\" = '$n' ]; then export GIT_AUTHOR_NAME=ALEXalesha; fi
  if [ \"\$GIT_COMMITTER_NAME\" = '$n' ]; then export GIT_COMMITTER_NAME=ALEXalesha; fi"
done
IDXF=""
if [ -s "$WORK/dirty.txt" ]; then
  IDXF="
  while IFS= read -r f; do
    mode=\$(git ls-tree \$GIT_COMMIT -- \"\$f\" | awk '{print \$1}')
    [ -n \"\$mode\" ] || continue
    blob=\$(git cat-file blob \$GIT_COMMIT:\"\$f\" | $CLEAN | git hash-object -w --stdin)
    git update-index --cacheinfo \$mode,\$blob,\"\$f\"
  done < '$WORK/dirty.txt'"
fi
PRUNE=()
if [ ${#DROP_PATHS[@]} -gt 0 ]; then
  printf '%s\n' "${DROP_PATHS[@]}" > "$WORK/drop.txt"
  IDXF="$IDXF
  while IFS= read -r p; do git rm --cached --ignore-unmatch -q -r -- \"\$p\" >/dev/null; done < '$WORK/drop.txt'" # drop:paths
  PRUNE=(--prune-empty)
fi
IDX=(); [ -n "$IDXF" ] && IDX=(--index-filter "$IDXF")

git branch -f "$BR" main
FILTER_BRANCH_SQUELCH_WARNING=1 git -c core.quotepath=off filter-branch -f -d "$WORK/rewrite" "${PRUNE[@]}" \
  --env-filter "$ENVF" --msg-filter "$CLEAN" "${IDX[@]}" "$BR" >/dev/null 2>&1 \
  || { echo "filter-branch не прошёл - пуш отменён (вывод не печатается: в нём может быть личное)" >&2; exit 1; }
git update-ref -d "refs/original/refs/heads/$BR" 2>/dev/null || true

# --- 2. проверки ---------------------------------------------------------------------------
git rev-list "$BR" > "$WORK/revs.txt"
git log "$BR" --format='%ae%n%ce%n%an%n%cn%n%B' > "$WORK/log.txt"
if hit grep -i -F -f "$GREPFILE" "$WORK/log.txt"; then # guard:private-log
  cancel "личное (почта, адрес Gitea, папка, имя) осталось в авторах или сообщениях коммитов"
fi
if hit grep -i -E "$PATH_RE" "$WORK/log.txt"; then # guard:path-msg
  cancel "путь к папке Drive остался в сообщениях коммитов"
fi
if rev_grep "$WORK/revs.txt" -I -l -i -F -f "$GREPFILE"; then # guard:private-files
  cancel "личное (почта, адрес Gitea, папка, имя) осталось в файлах публикуемой истории" show
fi
if rev_grep "$WORK/revs.txt" -I -l -i -E "$PATH_RE"; then # guard:path-files
  cancel "путь к папке Drive остался в файлах публикуемой истории" show
fi
if [ -n "$TEXT_FORBID" ]; then
  if hit grep -i -E "$TEXT_FORBID" "$WORK/log.txt"; then # guard:forbid-msg
    cancel "TEXT_FORBID в сообщениях коммитов"
  fi
  if rev_grep "$WORK/revs.txt" -I -n -i -E "$TEXT_FORBID"; then # guard:forbid-files
    cancel "TEXT_FORBID в файлах публикуемой истории" show
  fi
  # имена файлов тоже: grep по списку путей всей истории
  git log "$BR" --name-only --format= > "$WORK/paths.txt"
  if hit grep -i -E "$TEXT_FORBID" "$WORK/paths.txt"; then # guard:forbid-names
    cancel "TEXT_FORBID в именах файлов публикуемой истории" show
  fi
fi

# --- 3. теги GitHub, которые не ведут в свежую ветку --------------------------------------
# После чистки старые коммиты оставались бы видны через старые теги (к ним привязаны
# выпуски). Тег переставляется на коммит с тем же временем автора и заголовком.
git remote get-url github >/dev/null 2>&1 || git remote add github "https://github.com/$REPO.git"
MOVES=()
git for-each-ref --format='%(refname)' refs/github-tags | xargs -r -n1 git update-ref -d
git fetch -q github '+refs/tags/*:refs/github-tags/*' 2>/dev/null || true
git log "$BR" --format='%H %at %s' > "$WORK/keys.txt"
for ref in $(git for-each-ref --format='%(refname)' refs/github-tags); do
  name=${ref#refs/github-tags/}
  old=$(git rev-parse "$ref^{commit}")
  git merge-base --is-ancestor "$old" "$BR" && continue
  key=$(git log -1 --format='%at %s' "$old")
  new=$(awk -v k="$key" '{h=$1; $1=""; if (!f && substr($0,2)==k) {print h; f=1}}' "$WORK/keys.txt")
  if [ -z "$new" ]; then
    echo "тег $name: в публикуемой ветке нет коммита с тем же временем и заголовком - оставлен" >&2
    continue
  fi
  echo "тег $name: $(git rev-parse --short "$old") -> $(git rev-parse --short "$new")"
  MOVES+=("+$new:refs/tags/$name")
done
git for-each-ref --format='%(refname)' refs/github-tags | xargs -r -n1 git update-ref -d

echo "ветка $BR: $(wc -l < "$WORK/revs.txt") коммитов, $(git log -1 --format=%h "$BR"), main $(git rev-parse --short main) -> $REPO"
if [ "${DRY_RUN:-0}" = 1 ]; then
  echo "DRY_RUN=1: проверки пройдены, на GitHub ничего не отправлено"
  [ ${#MOVES[@]} -eq 0 ] || echo "теги переставились бы: ${MOVES[*]}"
  [ -z "$TAG" ] || echo "тег $TAG встал бы на $(git log -1 --format=%h "$BR")"
  exit 0
fi
case "$(git remote get-url github)" in https://github.com/*) gh auth setup-git ;; esac
git push github "$BR:main" --force
[ ${#MOVES[@]} -eq 0 ] || git push github "${MOVES[@]}"
if [ -n "$TAG" ]; then
  # Тег ставится прямо на GitHub, без локального: локальный указывал бы на переписанный
  # коммит github-main и путался с тегами Gitea.
  git push github "+$BR:refs/tags/$TAG"
  echo "тег $TAG отправлен"
fi
