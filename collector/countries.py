"""Códigos de país (IOC) usados pela FIP e MatchScorer, e mapeamento das bandeiras do site FIP."""

TARGET = "POR"

# Códigos IOC mais comuns no circuito + extras usados pela FIP (UAE em vez de UAE/ARE, etc.).
# Serve para distinguir "Nome Apelido POR" de marcas como "38 WC" ou "AWC".
IOC = set("""
AFG ALB ALG AND ANG ARG ARM AUS AUT AZE BAH BAN BAR BEL BEN BER BIH BLR BOL BOT BRA BRN BUL BUR CAN CHI CHN
CIV CMR COD COL CPV CRC CRO CUB CYP CZE DEN DOM ECU EGY ESA ESP EST ETH FIN FRA GAB GBR GEO GER GHA GRE GUA
HKG HON HUN INA IND IRI IRL IRQ ISL ISR ITA JAM JOR JPN KAZ KEN KGZ KOR KSA KUW LAT LBN LIE LTU LUX MAC MAD
MAR MAS MDA MEX MGL MKD MLT MNE MON MOZ MRI NAM NED NGR NOR NZL OMA PAK PAN PAR PER PHI PLE POL POR PUR QAT
ROU RSA RUS RWA SEN SGP SLO SMR SRB SRI SUI SVK SWE SYR THA TPE TUN TUR UAE UGA UKR URU USA UZB VEN VIE ZAM ZIM
IRN LIB MLD
""".split())

# Ficheiros de bandeira do site padelfip.com -> código. Só precisamos de saber se é Portugal,
# mas guardamos o nome do ficheiro para mostrar.
def nat_from_fip_flag(src: str) -> str:
    """'.../2023/02/Portugal_Fip.jpg' -> 'POR'; outros -> nome do país do ficheiro (ex. 'Spain')."""
    if not src:
        return ""
    name = src.rsplit("/", 1)[-1].split(".")[0]
    name = name.replace("_Fip", "").replace("Flag_of_", "")
    if name.lower().startswith("portugal"):
        return TARGET
    return name


def nat_from_ms_flag(src: str) -> str:
    """MatchScorer: '/images/flags/POR.jpg' -> 'POR'."""
    if not src:
        return ""
    return src.rsplit("/", 1)[-1].split(".")[0].upper()
