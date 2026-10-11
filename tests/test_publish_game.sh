#!/usr/bin/env bash
# Проверки tools/publish_game.sh на временных репозиториях: «GitHub» - локальный пустой
# репозиторий, ничего не уходит с ПК. Почта, адрес Gitea и имя - выдуманные.
#
#   bash tests/test_publish_game.sh             # все случаи (~10-15 мин на загруженном ПК)
#   bash tests/test_publish_game.sh a1 b        # только эти группы
#   bash tests/test_publish_game.sh --mutants   # каждая проверка убрана - случай краснеет
#
# Случаи:
#   a1     путь к папке Drive в шести написаниях в файле и в сообщении, почта, адрес Gitea,
#          имя в падежах - заменены, выкладка идёт; на выходе личного нет;
#   a2f-N  путь (написание N) остался в файле после чистки - падает;   a2m-N - в сообщении;
#   ea     почта в авторе (другой регистр, env-filter её не узнаёт), длинная история - падает;
#   em/ef  почта осталась в сообщении (длинный вывод git log) / в файле - падает;
#   b      TEXT_FORBID в 5000 строках файла - падает; bm - в сообщении; bn - в имени файла;
#   df/dm  имя (publish.privateName) осталось в файле / в сообщении - падает;
#   drop   DROP_PATHS вырезает файл из всей истории (слово TEXT_FORBID было только в нём);
#   chunk  личное в самом старом из 12 коммитов при кусках по 5 (PG_CHUNK) - падает;
#   push   без DRY_RUN: чистая ветка и тег уходят в «GitHub»; pushbad - путь остался,
#          в «GitHub» не ушло ничего.
# «Осталось после чистки» делается правилом TEXT_SED, которое вставляет строку обратно после
# всех замен: так проверка испытывается отдельно от замены.
set -uo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="${PUBLISH_GAME_DIR:-$HERE/tools}"
SD="$SRC_DIR"                                  # папка испытываемого скрипта (у мутантов - копия)
D=Dri; D="${D}ve"; A=Ale; A="${A}xey"           # путь склеивается из кусков, строкой его здесь нет
SPELL=(
  "C:\\$D\\$A\\Projects\\Web"
  "C:/$D/$A/Projects/Web"
  "/c/$D/$A/Projects"
  "C:\\\\$D\\\\$A\\\\Projects"
  "C--$D-$A-Projects-Apps"
  "c:\\${D,,}\\${A^^}"
)
EMAIL=tester@example.invalid
GITEA=gitea.test.lan:3000
FAKE_NAME="Ivan Testovich|Тимофе"               # выдуманное имя (полное и основа) для publish.privateName
PASS=0; FAIL=0; FAILED=()
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT                     # только свои временные папки

# sed-замена, вставляющая строку $1 (обратная косая, # и & экранированы)
sed_rep() { local r="${1//\\/\\\\}"; r="${r//#/\\#}"; printf '%s' "${r//&/\\&}"; }

# repo <имя> <publish.conf>: игра с origin на «Gitea» и remote github на пустой bare
repo() {
  local t="$ROOT/$1"
  rm -rf "$t"; mkdir -p "$t/games" && git init -q --bare "$t/gh.git"
  R="$t/games/G"; GH="$t/gh.git"; git init -q -b main "$R"
  git -C "$R" config user.email "$EMAIL"
  git -C "$R" config user.name tester
  git -C "$R" config core.autocrlf false
  git -C "$R" remote add origin "http://$GITEA/x/y.git"
  git -C "$R" remote add github "$GH"
  mkdir -p "$R/tools"
  # publish.conf не коммитится: в нём правила с самим личным, история должна быть без них
  printf 'REPO=ALEXalesha/T\n%s\n' "$2" > "$R/tools/publish.conf"
  printf 'tools/publish.conf\n' > "$R/.git/info/exclude"
}
# commit <путь> <содержимое> <сообщение> [почта автора] - коммит в main без рабочей копии
commit() {
  local idx="$ROOT/main.index" parent=()
  if git -C "$R" rev-parse -q --verify refs/heads/main >/dev/null; then
    GIT_INDEX_FILE="$idx" git -C "$R" read-tree refs/heads/main; parent=(-p refs/heads/main)
  else
    GIT_INDEX_FILE="$idx" git -C "$R" read-tree --empty
  fi
  local blob; blob=$(printf '%s\n' "$2" | git -C "$R" hash-object -w --stdin)
  GIT_INDEX_FILE="$idx" git -C "$R" update-index --add --cacheinfo "100644,$blob,$1"
  local tree; tree=$(GIT_INDEX_FILE="$idx" git -C "$R" write-tree)
  local c; c=$(printf '%s\n' "$3" | GIT_AUTHOR_EMAIL="${4:-$EMAIL}" git -C "$R" commit-tree "$tree" "${parent[@]}")
  git -C "$R" update-ref refs/heads/main "$c"
}
# run [DRY_RUN] [тег]
run() {
  git -C "$R" reset -q --hard main
  OUT=$(cd "$R" && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=publish.privateName GIT_CONFIG_VALUE_0="$FAKE_NAME" \
        PG_CHUNK="${CHUNK:-200}" DRY_RUN="${1:-1}" bash "$SD/publish_game.sh" . ${2:-} 2>&1); RC=$?
}
ok()  { PASS=$((PASS+1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL+1)); FAILED+=("$1"); echo "  FAIL $1: $2"; printf '%s\n' "$OUT" | tail -5 | sed 's/^/       /'; }
expect_fail() { # <случай> <часть сообщения>
  if [ "$RC" -ne 0 ] && printf '%s' "$OUT" | grep -F -- "$2" >/dev/null; then ok "$1"; else bad "$1" "ждали отказ «$2», код $RC"; fi
}
expect_pass() {
  if [ "$RC" -eq 0 ] && printf '%s' "$OUT" | grep -F "DRY_RUN=1: проверки пройдены" >/dev/null; then ok "$1"; else bad "$1" "ждали успех, код $RC"; fi
}
gh_empty() { [ -z "$(git -C "$GH" for-each-ref)" ]; }
BIG=$(seq 1 3000 | sed 's/^/filler line of a long old commit message /')   # > 64 КБ в git log

case_a1() {
  repo a1 ''
  local all; all=$(printf '%s\n' "${SPELL[@]}")
  commit README.md "start" "first commit$(printf '\n\n%s' "$BIG")"
  commit notes.md "$all
mail $EMAIL, gitea http://$GITEA/x, host ${GITEA%%:*}
написано Тимофеем, для Тимофея; Ivan Testovich; Testovich" "notes for $all, by Тимофей, $EMAIL"
  run; expect_pass a1
  [ "$RC" -eq 0 ] || return 0
  local revs; revs=$(git -C "$R" rev-list github-main)
  git -C "$R" log github-main --format='%ae%n%ce%n%an%n%cn%n%B' > "$ROOT/a1.log"
  # shellcheck disable=SC2086
  if git -C "$R" grep -I -i -E "$D([\\/]+|-+)$A" $revs -- >/dev/null \
     || grep -i -E "$D([\\/]+|-+)$A" "$ROOT/a1.log" >/dev/null; then
    bad a1-clean "путь остался в github-main"
  elif git -C "$R" grep -I -i -E "tester@|gitea\.test|Testovich|Тимофе" $revs -- >/dev/null \
       || grep -i -E "tester@|gitea\.test|Testovich|Тимофе" "$ROOT/a1.log" >/dev/null; then
    bad a1-clean "почта, адрес или имя остались в github-main"
  elif ! git -C "$R" show github-main:notes.md > "$ROOT/a1.notes" \
       || ! grep -F 'C:\Work\Projects\Web' "$ROOT/a1.notes" >/dev/null \
       || ! grep -F 'C--Work-Projects-Apps' "$ROOT/a1.notes" >/dev/null \
       || ! grep -F 'написано автором, для автора' "$ROOT/a1.notes" >/dev/null \
       || ! grep -F 'http://gitea.local/x' "$ROOT/a1.notes" >/dev/null; then
    bad a1-clean "в notes.md нет ожидаемых замен (C:\\Work, автором, gitea.local)"
  else ok a1-clean; fi
}
case_a2f() { # <номер написания>
  repo "a2f$1" "TEXT_GREP=MARKER
TEXT_SED=('s#MARKER#$(sed_rep "${SPELL[$1]}")#g')"
  commit notes.md "see MARKER here" "notes"
  run; expect_fail "a2f-$1" "путь к папке Drive остался в файлах"
}
case_a2m() {
  repo "a2m$1" "TEXT_SED=('s#MARKER#$(sed_rep "${SPELL[$1]}")#g')"
  commit README.md "start" "first commit$(printf '\n\n%s' "$BIG")"
  commit notes.md "clean" "notes MARKER"
  run; expect_fail "a2m-$1" "путь к папке Drive остался в сообщениях"
}
case_ea() {
  repo ea ''
  commit README.md "start" "first commit$(printf '\n\n%s' "$BIG")"
  commit notes.md "clean" "notes" "Tester@Example.INVALID"
  run; expect_fail ea "осталось в авторах или сообщениях"
}
case_em() {
  repo em "TEXT_SED=('s#MARKER#$EMAIL#g')"
  commit README.md "start" "first commit$(printf '\n\n%s' "$BIG")"
  commit notes.md "clean" "notes MARKER"
  run; expect_fail em "осталось в авторах или сообщениях"
}
case_ef() {
  repo ef "TEXT_GREP=MARKER
TEXT_SED=('s#MARKER#$EMAIL#g')"
  commit notes.md "mail MARKER" "notes"
  run; expect_fail ef "осталось в файлах"
}
case_b() {
  repo b 'TEXT_FORBID="Roblox-style"'
  commit web/a.js "$(seq 1 5000 | sed 's/$/ Roblox-style level/')" "page"
  commit web/b.js "x" "more"
  run; expect_fail b "TEXT_FORBID в файлах"
}
case_bm() {
  repo bm 'TEXT_FORBID="Roblox-style"'
  commit README.md "start" "first commit$(printf '\n\n%s' "$BIG")"
  commit notes.md "clean" "a roblox-style level"
  run; expect_fail bm "TEXT_FORBID в сообщениях"
}
case_bn() {
  repo bn 'TEXT_FORBID="Roblox-style"'
  commit docs/roblox-style.png.txt "x" "image"
  run; expect_fail bn "TEXT_FORBID в именах файлов"
}
case_df() {
  repo df "TEXT_GREP=MARKER
TEXT_SED=('s#MARKER#Ivan Testovich#g')"
  commit notes.md "by MARKER" "notes"
  run; expect_fail df "осталось в файлах"
}
case_dm() {
  repo dm "TEXT_SED=('s#MARKER#Тимофеем#g')"
  commit README.md "start" "first commit$(printf '\n\n%s' "$BIG")"
  commit notes.md "clean" "notes by MARKER"
  run; expect_fail dm "осталось в авторах или сообщениях"
}
case_drop() {
  repo drop 'DROP_PATHS=(docs/spec.md)
TEXT_FORBID="Roblox-style"'
  commit docs/spec.md "the name: Roblox-style" "spec"
  commit main.py "print(1)" "code"
  commit docs/spec.md "the name: Roblox-style, v2" "spec v2"
  run; expect_pass drop
  [ "$RC" -eq 0 ] || return 0
  if git -C "$R" log github-main --format=%H -- docs/spec.md > "$ROOT/drop.txt" && [ -s "$ROOT/drop.txt" ]; then
    bad drop-gone "docs/spec.md остался в истории"
  else ok drop-gone; fi
}
case_chunk() {
  repo chunk "TEXT_GREP=MARKER
TEXT_SED=('s#MARKER#$(sed_rep "${SPELL[0]}")#g')"
  commit old.md "MARKER" "old"
  local i; for i in $(seq 1 11); do commit "f$i.md" "$i" "c$i"; done
  commit old.md "gone" "old rewritten"
  CHUNK=5 run; expect_fail chunk "путь к папке Drive остался в файлах"
}
case_push() {
  repo push ''
  commit README.md "start" "first"
  commit notes.md "${SPELL[1]}" "notes"
  run 0 v9.9.9
  if [ "$RC" -eq 0 ] && git -C "$GH" rev-parse -q --verify refs/heads/main >/dev/null \
     && git -C "$GH" rev-parse -q --verify refs/tags/v9.9.9 >/dev/null; then ok push; else bad push "main и тег не ушли, код $RC"; fi
}
case_pushbad() {
  repo pushbad "TEXT_GREP=MARKER
TEXT_SED=('s#MARKER#$(sed_rep "${SPELL[1]}")#g')"
  commit notes.md "see MARKER" "notes"
  run 0 v9.9.9
  if [ "$RC" -ne 0 ] && gh_empty; then ok pushbad; else bad pushbad "ждали отказ и пустой GitHub, код $RC"; fi
}

IDX=("${!SPELL[@]}")
all_cases() { # [имена групп]
  local groups=("$@"); [ ${#groups[@]} -gt 0 ] || groups=(a1 a2f a2m ea em ef b bm bn df dm drop chunk push pushbad)
  local g i
  for g in "${groups[@]}"; do
    case $g in
      a2f|a2m) for i in "${IDX[@]}"; do "case_$g" "$i"; done ;;
      *) "case_$g" ;;
    esac
  done
}

# mutate <метка> <копия>: guard - проверка выключена; pipe - старая проверка конвейером
mutate() {
  local tag="$1" dir="$2" rep=""
  rm -rf "$dir"; mkdir -p "$dir"; cp "$SRC_DIR/publish_game.sh" "$SRC_DIR/publish_game_scrub.pl" "$dir/"
  case $tag in
    scrub:*|drop:*)
      sed -i "/# $tag/d" "$dir/publish_game.sh" "$dir/publish_game_scrub.pl" ;;
    guard:*)
      sed -i -E "/# $tag\$/s/^(\s*)if /\1if false \&\& /" "$dir/publish_game.sh" ;;
    pipe:private-log)
      rep='if git log "$BR" --format="%ae%n%ce%n%an%n%cn%n%B" | grep -qiF -f "$GREPFILE"; then # guard:private-log' ;;
    pipe:forbid-msg)
      rep='  if git log "$BR" --format=%B | grep -qi -E "$TEXT_FORBID"; then # guard:forbid-msg' ;;
    pipe:forbid-files)
      rep='  if git grep -I -n -i -E "$TEXT_FORBID" $(cat "$WORK/revs.txt") -- | head -5 | grep . >/dev/null; then # guard:forbid-files' ;;
  esac
  if [ -n "$rep" ]; then
    awk -v t="# guard:${tag#pipe:}" -v r="$rep" '{ if (substr($0, length($0) - length(t) + 1) == t) print r; else print }' \
      "$SRC_DIR/publish_game.sh" > "$dir/publish_game.sh"
  fi
}

if [ "${1:-}" = --mutants ]; then
  MUTANTS=(
    "scrub:path|a1"
    "drop:paths|drop"
    "guard:private-log|ea,em,dm"
    "pipe:private-log|em"
    "guard:path-msg|a2m"
    "guard:private-files|ef,df"
    "guard:path-files|a2f,chunk"
    "guard:forbid-msg|bm"
    "pipe:forbid-msg|bm"
    "guard:forbid-files|b"
    "pipe:forbid-files|b"
    "guard:forbid-names|bn"
  )
  KILLED=0; ALIVE=(); IDX=(1)
  for m in "${MUTANTS[@]}"; do
    tag="${m%%|*}"; groups="${m#*|}"
    SD="$ROOT/mutant"; mutate "$tag" "$SD"
    if cmp -s "$SRC_DIR/publish_game.sh" "$SD/publish_game.sh" && cmp -s "$SRC_DIR/publish_game_scrub.pl" "$SD/publish_game_scrub.pl"; then
      echo "мутант $tag: метки нет в скрипте"; ALIVE+=("$tag (нет метки)"); continue
    fi
    echo "мутант $tag:"
    FAIL=0
    # shellcheck disable=SC2086
    all_cases ${groups//,/ }
    SD="$SRC_DIR"
    if [ "$FAIL" -gt 0 ]; then KILLED=$((KILLED+1)); echo "  -> убит"; else ALIVE+=("$tag"); echo "  -> ЖИВ"; fi
  done
  echo "мутанты: убито $KILLED из ${#MUTANTS[@]}"
  [ ${#ALIVE[@]} -eq 0 ] || { echo "живые: ${ALIVE[*]}"; exit 1; }
  exit 0
fi

all_cases "$@"
echo "прошло $PASS, упало $FAIL"
[ "$FAIL" -eq 0 ] || { echo "упали: ${FAILED[*]}"; exit 1; }
