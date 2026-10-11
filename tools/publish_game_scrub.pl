# Убирает личное из текста (файл или сообщение коммита). Зовётся из publish_game.sh как
# perl -p; все строки приходят через окружение, \Q...\E экранирует их целиком. Порядок:
#   почта -> анонимная почта GitHub; адрес Gitea (с портом, потом без) -> gitea.local;
#   папка над игрой (PG_DIR, обе записи) -> убирается вместе с разделителем после неё
#     (C:/.../AiGames/DurakAiGame -> DurakAiGame, как в прежних scrub_private.pl);
#   папка Drive на ПК в любом написании -> Work с тем же разделителем (C:\Work, /c/Work,
#     C--Work-...), шаблон с первым именем из PG_PATH_NAME;
#   имя - PRIVATE_NAME: основы через |. Кириллическая основа меняется на «автор» в том же
#     падеже (окончания -й, -я, -ю, -ем, -е), латинская - на «the author»; у имени с пробелом
#     отдельно и последнее слово (фамилия). Основы короче 4 байт не трогаются.
# Само личное в этом файле не пишется.
BEGIN {
    $email  = $ENV{PG_EMAIL} // '';
    $pubem  = $ENV{PG_PUBLIC_EMAIL} // '';
    $gitea  = $ENV{PG_GITEA} // '';
    $ghost  = $ENV{PG_GITEA_HOST} // '';
    $fwd    = $ENV{PG_DIR} // '';
    $bck    = $ENV{PG_DIR_BS} // '';
    $pn     = $ENV{PG_PATH_NAME} // '';
    my @raw = map { my $s = $_; $s =~ s/^\s+|\s+$//g; $s } split /\|/, ($ENV{PRIVATE_NAME} // '');
    my @all;
    for my $n (@raw) {
        next unless length $n;
        push @all, $n;
        push @all, $1 if $n =~ /\s(\S+)$/;
    }
    # длинные сначала: полное имя раньше фамилии
    @names = sort { length($b) <=> length($a) } grep { length($_) >= 4 } @all;
    %ru = ("\xd0\xb5\xd0\xbc" => "\xd0\xb0\xd0\xb2\xd1\x82\xd0\xbe\xd1\x80\xd0\xbe\xd0\xbc",   # -ем -> автором
           "\xd0\xb9" => "\xd0\xb0\xd0\xb2\xd1\x82\xd0\xbe\xd1\x80",                             # -й  -> автор
           "\xd1\x8f" => "\xd0\xb0\xd0\xb2\xd1\x82\xd0\xbe\xd1\x80\xd0\xb0",                     # -я  -> автора
           "\xd1\x8e" => "\xd0\xb0\xd0\xb2\xd1\x82\xd0\xbe\xd1\x80\xd1\x83",                     # -ю  -> автору
           "\xd0\xb5" => "\xd0\xb0\xd0\xb2\xd1\x82\xd0\xbe\xd1\x80\xd0\xb5");                    # -е  -> авторе
}
s/\Q$email\E/$pubem/gi if length $email >= 4;
s/\Q$gitea\E/gitea.local/gi if length $gitea >= 4;
s/\Q$ghost\E/gitea.local/gi if length $ghost >= 4;
s/\Q$bck\E\\?//gi if length $bck >= 4;
s/\Q$fwd\E\/?//gi if length $fwd >= 4;
if (length $pn) {                                                         # scrub:path
    s{([a-z]:|/[a-z])([\\/]+)drive[\\/]+\Q$pn\E}{$1$2Work}gi;            # scrub:path
    s{([a-z])--drive-+\Q$pn\E}{$1--Work}gi;                               # scrub:path
    s{drive(?:[\\/]+|-+)\Q$pn\E}{Work}gi;                                 # scrub:path
}                                                                         # scrub:path
for my $n (@names) {
    if ($n =~ /[\xd0\xd1]/) {
        s/\Q$n\E(\xd0\xb5\xd0\xbc|\xd0\xb9|\xd1\x8f|\xd1\x8e|\xd0\xb5)/$ru{$1}/g;
        s/\Q$n\E/\xd0\xb0\xd0\xb2\xd1\x82\xd0\xbe\xd1\x80/g;
    } else {
        s/\Q$n\E/the author/gi;
    }
}
