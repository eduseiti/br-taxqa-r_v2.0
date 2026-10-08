<?xml version="1.0" encoding="UTF-8"?>
<!--
    Amended copy of GeraCSVporArtigoPorAgrupador.xsl (verbatim original in this folder).
    Amendments X1-X9 of docs/20260924_123747_segmentation_implementation_plan.md §3.1:

    X1  param `metadados` (full prefix computed in Python, common.metadata_for); fallback
        Epigrafe | Ementa of the document itself when the parameter is empty.
    X2  no NomeAgrupador in the prefix: every row is "[ metadados ] CAMINHO CONTEUDO".
    X3  one ancestor-path function lx:caminho (Rotulo + TituloDispositivo + string() of the own p of
        each dispositivo ancestor; string(), not p/text(), so span/Remissao text is kept).
    X3b caput sentence inserted after the article label for units inside a Paragrafo (and PAR rows).
        Switchable since 2026-10-05 (caput plan D-A/D-B, docs/20261005_184116_*): param
        `caput_em_paragrafo` = 'nao' (default: no caput text; S1-S3 `base` rows) | 'frase' (the caput's
        own p after the label; the S4/S2c `caput` variant, produced in Python by add_caput_variants.py).
    X4  one content function lx:texto (own Rotulo, TituloDispositivo, NomeAgrupador, p and tables,
        then the same for every descendant, in document order).
    X5  CPT and PAR iterated independently; CPT only when the article has a Paragrafo.
    X6  DSP row for every top-level orphan dispositivo (Caput/Paragrafo/Inciso/Alinea/Item with no
        dispositivo ancestor), in every document; it is the root of lx:caminho for its descendants.
    X7  one label function lx:rotulo (fixes the Subitulo typo, the "caput, ," double comma and the
        substring-before() labels that were empty for '-', '—' or no separator).
    X8  tables serialized into the text (lx:tabela): "Tabela: c1 | c2 ; c1 | c2 ...".
    X9  every string column is CSV-escaped (lx:csv).
    calculaPos is kept verbatim (interval numbering contract, regression-tested).
    The Python mirror of lx:texto / lx:caminho / lx:tabela is in common.py (parity-tested).
-->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:math="http://www.w3.org/2005/xpath-functions/math"
    exclude-result-prefixes="xs math" xmlns:lx="http://www.lexml.gov.br/1.0"  xmlns="http://www.lexml.gov.br/1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xpath-default-namespace="http://www.lexml.gov.br/1.0"
    version="3.0">


    <xsl:variable name="uri" select="document-uri(/)"/>
    <xsl:variable name="filename"
        select="replace($uri, '^.*/', '')"/>

    <xsl:output method="text" omit-xml-declaration="yes"/>
    <xsl:param name="sigla"><xsl:value-of select="substring-before($filename, '.xml')"/></xsl:param>
    <!-- X1: full metadata prefix, computed once in Python (common.metadata_for) -->
    <xsl:param name="metadados" as="xs:string" select="''"/>
    <!-- X3b (caput plan D-A): 'nao' = paragraph-family paths carry no caput text; 'frase' = old X3b -->
    <xsl:param name="caput_em_paragrafo" as="xs:string" select="'nao'"/>

    <xsl:variable name="meta" as="xs:string" select="if (normalize-space($metadados) ne '')
        then normalize-space($metadados)
        else string-join((normalize-space(string((//Epigrafe)[1])), normalize-space(string((//Ementa)[1])))[. ne ''], ' | ')"/>
    <xsl:variable name="prefixo" as="xs:string" select="if ($meta ne '') then concat('[ ', $meta, ' ] ') else '[ ] '"/>
    <xsl:variable name="urnDoc" as="xs:string" select="string(/LexML/Metadado[1]/Identificacao[1]/@URN)"/>

    <xsl:template name="calculaPos">
        <xsl:variable name="qtPrec" select="count(preceding::Artigo[not(ancestor::Alteracao)]|preceding::Caput[not(ancestor::Alteracao)]|preceding::Paragrafo[not(ancestor::Alteracao)]|preceding::Parte[not(ancestor::Alteracao)]|preceding::Livro[not(ancestor::Alteracao)]|preceding::Titulo[not(ancestor::Alteracao)]|preceding::Subtitulo[not(ancestor::Alteracao)]|preceding::Capitulo[not(ancestor::Alteracao)]|preceding::Secao[not(ancestor::Alteracao)]|preceding::Subsecao[not(ancestor::Alteracao)]|preceding::Inciso[not(ancestor::Alteracao)]|preceding::Alinea[not(ancestor::Alteracao)]|preceding::Item[not(ancestor::Alteracao)]) "/>
        <xsl:variable name="qtAnc" select="count(ancestor::Artigo[not(ancestor::Alteracao)]|ancestor::Caput[not(ancestor::Alteracao)]|ancestor::Paragrafo[not(ancestor::Alteracao)]|ancestor::Parte[not(ancestor::Alteracao)]|ancestor::Livro[not(ancestor::Alteracao)]|ancestor::Titulo[not(ancestor::Alteracao)]|ancestor::Subtitulo[not(ancestor::Alteracao)]|ancestor::Capitulo[not(ancestor::Alteracao)]|ancestor::Secao[not(ancestor::Alteracao)]|ancestor::Subsecao[not(ancestor::Alteracao)]|ancestor::Inciso[not(ancestor::Alteracao)]|ancestor::Alinea[not(ancestor::Alteracao)]|ancestor::Item[not(ancestor::Alteracao)]) "/>
        <xsl:variable name="qtF" select="count(descendant::Artigo[not(ancestor::Alteracao)]|descendant::Caput[not(ancestor::Alteracao)]|descendant::Paragrafo[not(ancestor::Alteracao)]|descendant::Parte[not(ancestor::Alteracao)]|descendant::Livro[not(ancestor::Alteracao)]|descendant::Titulo[not(ancestor::Alteracao)]|descendant::Subtitulo[not(ancestor::Alteracao)]|descendant::Capitulo[not(ancestor::Alteracao)]|descendant::Secao[not(ancestor::Alteracao)]|descendant::Subsecao[not(ancestor::Alteracao)]|descendant::Inciso[not(ancestor::Alteracao)]|descendant::Alinea[not(ancestor::Alteracao)]|descendant::Item[not(ancestor::Alteracao)])"/>
        <xsl:value-of select="($qtPrec * 2) + $qtAnc +1"/><xsl:text>,</xsl:text><xsl:value-of select="($qtPrec * 2) + $qtAnc + 1 + ($qtF * 2) + 1"/><xsl:text>,</xsl:text>
    </xsl:template>

    <!-- X9: CSV field, always quoted, inner quotes doubled -->
    <xsl:function name="lx:csv" as="xs:string">
        <xsl:param name="s" as="xs:string"/>
        <xsl:sequence select="concat('&quot;', replace($s, '&quot;', '&quot;&quot;'), '&quot;')"/>
    </xsl:function>

    <!-- X8: table serialization; cells ' | ', rows ' ; ', header row(s) first (document order) -->
    <xsl:function name="lx:tabela" as="xs:string">
        <xsl:param name="t" as="element()"/>
        <xsl:sequence select="normalize-space(concat('Tabela: ', string-join(
            for $r in $t//tr return string-join(for $c in $r/td return normalize-space(string($c)), ' | '),
            ' ; ')))"/>
    </xsl:function>

    <!-- X4: own Rotulo / TituloDispositivo / NomeAgrupador / p / table, then the same for every
         descendant, in document order (Alteracao content included, as in the original ART text) -->
    <xsl:function name="lx:texto" as="xs:string">
        <xsl:param name="n" as="element()"/>
        <xsl:sequence select="normalize-space(string-join(
            for $x in $n/descendant-or-self::*[self::Rotulo or self::TituloDispositivo or self::NomeAgrupador or self::p or self::table][not(ancestor::table)]
            return (if ($x/self::table) then lx:tabela($x) else normalize-space(string($x))),
            ' '))"/>
    </xsl:function>

    <!-- X3/X3b: ancestor path. For each dispositivo ancestor: its Rotulo, TituloDispositivo and own p
         (string(), so span/Remissao text is kept). With caput_em_paragrafo='frase', for units inside a
         Paragrafo of an article (and for the Paragrafo itself), the caput's own p follows the article
         label. -->
    <xsl:function name="lx:caminho" as="xs:string">
        <xsl:param name="n" as="element()"/>
        <xsl:variable name="ancs" select="$n/ancestor::*[self::Artigo or self::Caput or self::Paragrafo or self::Inciso or self::Alinea or self::Item]"/>
        <xsl:variable name="emPar" as="xs:boolean" select="$caput_em_paragrafo eq 'frase' and exists($n/ancestor-or-self::Paragrafo[parent::Artigo])"/>
        <xsl:sequence select="normalize-space(string-join(
            for $a in $ancs return (
                (for $x in $a/(Rotulo|TituloDispositivo|p) return normalize-space(string($x))),
                (if ($emPar and $a/self::Artigo) then (for $x in $a/Caput/p return normalize-space(string($x))) else ())
            ), ' '))"/>
    </xsl:function>

    <!-- X7: short label of an enumeration: "II –" -> "II", "b)" -> "b", "10." -> "10" -->
    <xsl:function name="lx:curto" as="xs:string">
        <xsl:param name="r" as="xs:string"/>
        <xsl:sequence select="replace(normalize-space($r), '^\s*([^\s–—\-).]+).*$', '$1')"/>
    </xsl:function>

    <xsl:function name="lx:componente" as="xs:string">
        <xsl:param name="d" as="element()"/>
        <xsl:sequence select="
            if ($d/self::Caput) then 'caput'
            else if ($d/self::Inciso) then concat('Inciso ', lx:curto(string($d/Rotulo[1])))
            else if ($d/self::Alinea) then concat('Alínea ', lx:curto(string($d/Rotulo[1])))
            else if ($d/self::Item) then concat('Item ', lx:curto(string($d/Rotulo[1])))
            else normalize-space(string($d/Rotulo[1]))"/>
    </xsl:function>

    <!-- X7: Rotulo column = sigla + path of labels (groupings: grouping path; dispositivos: dispositivo path) -->
    <xsl:function name="lx:rotulo" as="xs:string">
        <xsl:param name="n" as="element()"/>
        <xsl:param name="sigla" as="xs:string"/>
        <xsl:variable name="partes" as="xs:string*" select="
            if ($n/self::Parte or $n/self::Livro or $n/self::Titulo or $n/self::Subtitulo or $n/self::Capitulo or $n/self::Secao or $n/self::Subsecao)
            then (for $g in $n/ancestor-or-self::*[self::Parte or self::Livro or self::Titulo or self::Subtitulo or self::Capitulo or self::Secao or self::Subsecao] return normalize-space(string($g/Rotulo[1])))
            else (for $d in $n/ancestor-or-self::*[self::Artigo or self::Caput or self::Paragrafo or self::Inciso or self::Alinea or self::Item] return lx:componente($d))"/>
        <xsl:sequence select="string-join(($sigla, $partes[. ne '']), ', ')"/>
    </xsl:function>

    <xsl:function name="lx:temAncDisp" as="xs:boolean">
        <xsl:param name="n" as="element()"/>
        <xsl:sequence select="exists($n/ancestor::*[self::Artigo or self::Caput or self::Paragrafo or self::Inciso or self::Alinea or self::Item])"/>
    </xsl:function>

    <!-- one CSV row for the context node -->
    <xsl:template name="linha">
        <xsl:param name="tipo" as="xs:string"/>
        <xsl:value-of select="lx:csv($tipo)"/><xsl:text>,</xsl:text>
        <xsl:value-of select="lx:csv(lx:rotulo(., string($sigla)))"/><xsl:text>,</xsl:text>
        <xsl:call-template name="calculaPos"/>
        <xsl:value-of select="lx:csv(concat($prefixo, normalize-space(concat(lx:caminho(.), ' ', lx:texto(.)))))"/><xsl:text>,</xsl:text>
        <xsl:value-of select="lx:csv(concat($urnDoc, '!', @id))"/>
        <xsl:text>&#10;</xsl:text>
    </xsl:template>

    <xsl:template match="/">
        <xsl:text>"Tipo","Rotulo","Num_Inicio","Num_Final","Texto","urn"</xsl:text><xsl:text>&#10;</xsl:text>
        <!-- X5: CPT only when the article has a Paragrafo (otherwise it duplicates ART) -->
        <xsl:for-each select="//Caput[parent::Artigo][not(ancestor::Alteracao)][../Paragrafo[not(ancestor::Alteracao)]]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'CPT'"/></xsl:call-template>
        </xsl:for-each>
        <!-- X5: every Paragrafo under a dispositivo (top-level orphan Paragrafos are DSP) -->
        <xsl:for-each select="//Paragrafo[not(ancestor::Alteracao)][lx:temAncDisp(.)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'PAR'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Artigo[not(ancestor::Alteracao)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'ART'"/></xsl:call-template>
        </xsl:for-each>
        <!-- X6: top-level orphan dispositivos -->
        <xsl:for-each select="//*[self::Caput or self::Paragrafo or self::Inciso or self::Alinea or self::Item][not(ancestor::Alteracao)][not(lx:temAncDisp(.))]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'DSP'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Parte[not(ancestor::Alteracao)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'PRT'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Livro[not(ancestor::Alteracao)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'LIV'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Titulo[not(ancestor::Alteracao)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'TIT'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Subtitulo[not(ancestor::Alteracao)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'SBT'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Capitulo[not(ancestor::Alteracao)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'CAP'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Secao[not(ancestor::Alteracao)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'SEC'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Subsecao[not(ancestor::Alteracao)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'SSC'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Inciso[not(ancestor::Alteracao)][lx:temAncDisp(.)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'INC'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Alinea[not(ancestor::Alteracao)][lx:temAncDisp(.)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'ALI'"/></xsl:call-template>
        </xsl:for-each>
        <xsl:for-each select="//Item[not(ancestor::Alteracao)][lx:temAncDisp(.)]">
            <xsl:call-template name="linha"><xsl:with-param name="tipo" select="'ITE'"/></xsl:call-template>
        </xsl:for-each>
    </xsl:template>
</xsl:stylesheet>
