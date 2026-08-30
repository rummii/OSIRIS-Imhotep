"""Static regulatory & industry text corpus for OSIRIS Phase 1 RAG.

Hand-curated, **general reference** seed of Philippine regulatory text and
industry engineering standards.  Every chunk carries metadata
(``source, domain, jurisdiction, citation``) so retrieval can filter by
domain and the LLM can cite the originating document.

**GENERAL REFERENCE — VERIFY WITH PRIMARY SOURCE.**  Suitable as a context
hint for AI generation; for any binding compliance question, consult the
original government / industry publication.

To extend: append entries to ``CORPUS``; the next
``POST /api/admin/rag/refresh`` will chunk, embed, and index them.
"""
from __future__ import annotations

from typing import TypedDict


class Chunk(TypedDict):
    text: str
    source: str
    domain: str
    jurisdiction: str
    citation: str


CORPUS: list[Chunk] = [

    # ============================================================
    # CONSTRUCTION SAFETY (DOLE + RA 11058)
    # ============================================================
    {
        "text": (
            "DOLE Department Order No. 13, series of 1998 (Construction Safety "
            "and Health Program) requires all construction project owners to "
            "designate a full-time Construction Safety and Health (CSH) officer "
            "for projects with a total work force of 50 or more. The CSH officer "
            "must hold a valid Occupational Safety and Health Practitioner (OSHP) "
            "certification issued by DOLE or an OSHC-accredited training "
            "institution. Duties include: conducting daily toolbox meetings; "
            "supervising compliance with PPE requirements; maintaining an "
            "accident / incident register; coordinating with DOLE inspectors "
            "during site visits."
        ),
        "source": "dole-do-13",
        "domain": "construction_safety",
        "jurisdiction": "Philippines",
        "citation": "DOLE D.O. No. 13, s. 1998, Sec. 4 (Safety Officer)",
    },
    {
        "text": (
            "PPE for construction workers under DOLE D.O. No. 13 and RA 11058 "
            "must include, at minimum: hard hat (ANSI Z89.1 or equivalent), "
            "safety eyewear (Z87.1), high-visibility vest (Class 2 minimum for "
            "roadway work, Class 3 for night work), steel-toe boots, and "
            "task-specific gloves. Fall protection (full-body harness with "
            "shock-absorbing lanyard) is mandatory for any work above 1.8 "
            "metres. Respiratory protection (N95 minimum) is required for "
            "dust-generating activities such as concrete cutting, grinding, "
            "or demolition."
        ),
        "source": "dole-do-13",
        "domain": "construction_safety",
        "jurisdiction": "Philippines",
        "citation": "DOLE D.O. No. 13, s. 1998, Rule 1080 (PPE)",
    },
    {
        "text": (
            "Republic Act 11058 (Occupational Safety and Health Standards Act, "
            "2018) strengthened penalties for non-compliance with safety "
            "standards. Establishments must: provide a safe workplace and "
            "adequate safety training; report serious injuries to DOLE within "
            "24 hours; maintain a Safety and Health Committee for workplaces "
            "with 20 or more employees; comply with OSH standards set by DOLE. "
            "Penalties range from PHP 20,000 to PHP 100,000 per violation, "
            "with possible criminal liability for willful non-compliance "
            "resulting in death or serious injury."
        ),
        "source": "ra-11058",
        "domain": "construction_safety",
        "jurisdiction": "Philippines",
        "citation": "RA 11058, Sec. 6-12 (Duties, Reporting, Penalties)",
    },
    {
        "text": (
            "DOLE D.O. No. 198-18 (Implementing Rules of RA 11058) requires "
            "construction safety training for all workers before deployment. "
            "Mandatory modules: General Safety Orientation (4 hours); "
            "Construction Safety (8 hours); task-specific training for high-"
            "risk activities (scaffolding, confined space, hot work, working "
            "at height, electrical work). Workers must carry a BWCID-style "
            "safety training card at all times on site."
        ),
        "source": "dole-do-198-18",
        "domain": "construction_safety",
        "jurisdiction": "Philippines",
        "citation": "DOLE D.O. No. 198-18, Sec. 7 (Safety Training)",
    },

    # ============================================================
    # BUILDING CODE (PD 1096)
    # ============================================================
    {
        "text": (
            "Presidential Decree No. 1096 (National Building Code of the "
            "Philippines, 1977) classifies buildings by type and use (Groups A "
            "through J) and prescribes minimum design loads, fire resistance "
            "ratings, and means of egress. Group A (residential) dwellings must "
            "have a minimum live load of 1.9 kPa (40 psf) for bedrooms, 2.4 kPa "
            "(50 psf) for living areas, and stairs of 3.0 kPa (60 psf). All "
            "buildings exceeding 4 storeys or 15 metres height require a fire "
            "detection and alarm system per NFPA 72, plus at least one fire "
            "elevator sized to carry a stretcher."
        ),
        "source": "pd-1096",
        "domain": "building_code",
        "jurisdiction": "Philippines",
        "citation": "PD 1096, Chapter 5 (Loads and Sec. 505)",
    },
    {
        "text": (
            "PD 1096 requires that structural design of buildings in the "
            "Philippines follow the National Structural Code of the Philippines "
            "(NSCP). The NSCP references: NSCP 2015 Vol. 1 (Buildings, Towers, "
            "and Other Vertical Structures) for general design; NSCP 2015 Vol. 2 "
            "(Bridges) for infrastructure; and special volumes for towers, "
            "signboards, and other structures. Seismic design must follow the "
            "latest edition; the Philippines is in Seismic Zone 4 (highest) "
            "and most of Metro Manila falls in Soil Profile Type Sd (soft soil) "
            "per NSCP."
        ),
        "source": "pd-1096",
        "domain": "structural",
        "jurisdiction": "Philippines",
        "citation": "PD 1096, Sec. 402 (Reference Standards)",
    },
    {
        "text": (
            "Means of egress under PD 1096 (and Rule VII of the IRR) requires: "
            "minimum 1.0 m corridor width for up to 60 occupants, 1.2 m for "
            "60-200, 1.5 m for 200-300, and 1.8 m for over 300. Travel distance "
            "to an exit must not exceed 60 m for unsprinklered and 75 m for "
            "sprinklered buildings. Stairways must be at least 1.1 m wide with "
            "100 mm minimum handrail projection; risers 150-180 mm, treads "
            "250-300 mm. Emergency lighting must provide 10 lux at floor level "
            "for at least 90 minutes."
        ),
        "source": "pd-1096",
        "domain": "building_code",
        "jurisdiction": "Philippines",
        "citation": "PD 1096 IRR, Rule VII (Means of Egress)",
    },


    # ============================================================
    # DPWH STANDARD SPECIFICATIONS
    # ============================================================
    {
        "text": (
            "DPWH Standard Specifications for Highways, Bridges, and Airports "
            "(2013 edition, with updates through 2020) define the standard pay "
            "items, units of measurement, and method of measurement for public "
            "infrastructure works. Common items: Item 100 (Clearing and Grubbing) "
            "measured by hectare; Item 201 (Excavation) by cubic metre; Item 311 "
            "(Portland Cement Concrete Pavement) by square metre; Item 405 "
            "(Reinforcing Steel) by kilogram. Variation orders are governed by "
            "Annex E of the DPWH D.O. 197-2016."
        ),
        "source": "dpwh-do-197",
        "domain": "civil_works",
        "jurisdiction": "Philippines",
        "citation": "DPWH D.O. 197, s. 2016, Annex E (Variation Orders)",
    },
    {
        "text": (
            "DPWH D.O. 175, s. 2016 (Revised Guidelines on the Implementation of "
            "Infrastructure Projects) sets the standard procurement thresholds: "
            "below PHP 5 million = SVP (small value procurement); PHP 5M-50M = "
            "public bidding; above PHP 50M = public bidding with foreign-"
            "assisted component rules. Contractors must be PCAB-licensed and "
            "sized to the ABC (Approved Budget for the Contract). Project "
            "duration is governed by Annex I (network diagram) and Annex J "
            "(detailed unit cost analysis) submissions."
        ),
        "source": "dpwh-do-175",
        "domain": "civil_works",
        "jurisdiction": "Philippines",
        "citation": "DPWH D.O. 175, s. 2016 (Procurement Thresholds)",
    },

    # ============================================================
    # ELECTRICAL CODE (PEC 2017)
    # ============================================================
    {
        "text": (
            "The Philippine Electrical Code (PEC) 2017 (Part 1 & 2) is the "
            "national standard for safe electrical design, installation, and "
            "inspection. Key design rules: branch circuits in residential "
            "dwellings limited to 12 outlets or 80 percent of the breaker "
            "rating; GFCI protection required for bathrooms, kitchens, "
            "outdoor, and wet locations; AFCI protection for bedrooms "
            "(210.12); minimum wire size 2.0 mm-squared (14 AWG) for lighting, "
            "3.5 mm-squared (12 AWG) for outlets. Service entrance must be "
            "sized for the calculated load with 25 percent future expansion."
        ),
        "source": "pec-2017",
        "domain": "electrical_code",
        "jurisdiction": "Philippines",
        "citation": "PEC 2017, Article 2.10 (Branch Circuits)",
    },
    {
        "text": (
            "PEC 2017 grounding requirements: a single grounding electrode "
            "system with resistance to earth not exceeding 5 ohms for "
            "lightning protection, 25 ohms for typical installations. All "
            "metallic water pipes, building steel, and concrete-encased "
            "electrodes (20 ft of 6 AWG copper or 4 AWG rebar) must be "
            "bonded to the grounding electrode conductor. Sensitive "
            "electronics (data centers, hospitals) require isolated grounding "
            "per IEEE 1100."
        ),
        "source": "pec-2017",
        "domain": "electrical_code",
        "jurisdiction": "Philippines",
        "citation": "PEC 2017, Article 2.50 (Grounding and Bonding)",
    },

    # ============================================================
    # HVAC / MECHANICAL
    # ============================================================
    {
        "text": (
            "ASHRAE Standard 62.1-2019 (Ventilation for Acceptable Indoor Air "
            "Quality) sets minimum outdoor air flow rates per occupant for "
            "commercial spaces: offices 8.5 L/s per person plus 0.6 L/s per m2; "
            "classrooms 5.0 L/s per person plus 0.6 L/s per m2; retail 3.8 L/s "
            "per person plus 0.6 L/s per m2. In the Philippines this is "
            "enforced via the Green Building Code (GB-1 of the IRR of PD 1096). "
            "Filtration minimum MERV 8 for return air, MERV 13 for outdoor air "
            "in hospitals and clean rooms."
        ),
        "source": "ashrae-62-1",
        "domain": "hvac_mechanical",
        "jurisdiction": "International",
        "citation": "ASHRAE 62.1-2019, Table 6.2.2.1 (Ventilation Rates)",
    },
    {
        "text": (
            "Fire protection for HVAC systems per NFPA 90A: ductwork must be "
            "constructed of non-combustible materials; fire dampers required "
            "at every penetration of a 2-hour fire-rated wall or floor; smoke "
            "dampers required in corridors and rated smoke barriers. Kitchen "
            "exhaust must be separate from general exhaust and equipped with "
            "grease filters plus a fire suppression nozzle in the hood plenum. "
            "Smoke control systems for atriums must provide 10 air changes "
            "per hour of exhaust during fire mode."
        ),
        "source": "nfpa-90a",
        "domain": "hvac_mechanical",
        "jurisdiction": "International",
        "citation": "NFPA 90A-2021, Sec. 5.3 (Dampers)",
    },

    # ============================================================
    # IT INFRASTRUCTURE
    # ============================================================
    {
        "text": (
            "TIA-942-B (Telecommunications Infrastructure Standard for Data "
            "Centers, 2017) classifies data centers into four Tiers (I-IV) "
            "based on redundancy and concurrent maintainability. Tier III: "
            "concurrently maintainable with N+1 redundancy on every critical "
            "component; 99.982 percent availability; 1.6 hours downtime per "
            "year. Tier IV: fault-tolerant; 2N+1; 99.995 percent availability; "
            "26.3 minutes downtime per year. Data center design must address "
            "power, cooling, telecommunications, security, and fire "
            "suppression as integrated systems."
        ),
        "source": "tia-942",
        "domain": "it_infrastructure",
        "jurisdiction": "International",
        "citation": "TIA-942-B, Sec. 5 (Data Center Topology)",
    },
    {
        "text": (
            "Structured cabling per TIA-568 (Commercial Building "
            "Telecommunications Cabling) and TIA-569 (Pathways and Spaces) for "
            "IT infrastructure in commercial buildings. Horizontal cable runs "
            "must not exceed 90 m (295 ft) from the telecommunications room "
            "outlet to the work area. Backbone cabling: 100 m multimode OM3/OM4 "
            "or OS2 single-mode fiber. Work area outlets: minimum 2 ports "
            "(1 data, 1 voice) per workstation, with Cat 6A recommended for "
            "new builds to support 10 Gb/s."
        ),
        "source": "tia-568",
        "domain": "it_infrastructure",
        "jurisdiction": "International",
        "citation": "TIA-568-D, Sec. 6 (Horizontal Cabling)",
    },


    # ============================================================
    # FIRE PROTECTION
    # ============================================================
    {
        "text": (
            "NFPA 25 (Standard for the Inspection, Testing, and Maintenance of "
            "Water-Based Fire Protection Systems, 2020) sets the inspection "
            "intervals for sprinkler systems: weekly gauge check; monthly valve "
            "inspection; quarterly alarm device test; annual main drain test; "
            "5-year internal pipe inspection; 10-year hydrostatic test for "
            "dry-pipe systems. In the Philippines, RA 9514 (Fire Code of the "
            "Philippines, 2008) mandates automatic sprinkler systems for "
            "buildings exceeding 15 m height or 5,000 m2 gross floor area."
        ),
        "source": "nfpa-25",
        "domain": "fire_protection",
        "jurisdiction": "Philippines",
        "citation": "RA 9514 (Fire Code), Sec. 9; NFPA 25-2020, Ch. 4",
    },
    {
        "text": (
            "RA 9514 (Fire Code of the Philippines) requires all buildings to "
            "have: at least one fire exit per 60 m of travel distance; fire "
            "extinguishers sized per hazard classification (Class A: one 2-A "
            "extinguisher per 600 m2; Class B: one 10-B per 150 m2); automatic "
            "smoke detection in sleeping accommodations; standpipes with 100 mm "
            "risers in buildings over 23 m; annual fire safety inspection by "
            "the Bureau of Fire Protection (BFP) and issuance of a Fire Safety "
            "Inspection Certificate (FSIC)."
        ),
        "source": "ra-9514",
        "domain": "fire_protection",
        "jurisdiction": "Philippines",
        "citation": "RA 9514, Sec. 4-9 (Fire Safety Requirements)",
    },

    # ============================================================
    # COSTING / PRICE REFERENCES (text summaries, not live data)
    # ============================================================
    {
        "text": (
            "DTI Price Monitoring Division publishes weekly Suggested Retail "
            "Prices (SRP) for basic construction materials in major Philippine "
            "regions (NCR, Luzon, Visayas, Mindanao). Indicative unit costs "
            "(subject to regional variation): Portland cement 40 kg bag PHP "
            "280-320; 1-inch by 1-inch by 8-foot coco lumber PHP 250-320 per "
            "piece; 10 mm diameter reinforcing steel bar PHP 280-310 per "
            "length; 4-inch CHB PHP 18-22 per piece. These are reference "
            "values only and do not supersede contractor quotations or DPWH "
            "unit cost analyses."
        ),
        "source": "dti-srp",
        "domain": "costing",
        "jurisdiction": "Philippines",
        "citation": "DTI SRP weekly price index (general reference)",
    },
    {
        "text": (
            "For facilities engineering cost estimating, Philippine national "
            "average rates (subject to regional uplift) per PhilGEPS and DPWH "
            "reference: skilled laborer PHP 600-800 per day; leadman PHP "
            "850-1100 per day; foreman PHP 1200-1500 per day; safety officer "
            "PHP 1500-1800 per day; licensed electrician or mechanic PHP "
            "1200-1600 per day. Equipment rental: 1 cubic m backhoe PHP "
            "8000-12000 per day; 5-ton crane PHP 18000-25000 per day; 20 kVA "
            "generator PHP 3500-5000 per day. These are general industry "
            "indicators, not contractual rates."
        ),
        "source": "philgeps-reference",
        "domain": "costing",
        "jurisdiction": "Philippines",
        "citation": "PhilGEPS / DPWH reference rates (general industry average)",
    },
]


def get_corpus() -> list[Chunk]:
    """Return a copy of the seed corpus."""
    return list(CORPUS)


def corpus_domains() -> list[str]:
    """Return the unique domain list, sorted."""
    return sorted({chunk["domain"] for chunk in CORPUS})


def corpus_sources() -> list[dict]:
    """Return a summary of unique sources with domain and jurisdiction."""
    seen: dict[str, dict] = {}
    for chunk in CORPUS:
        if chunk["source"] not in seen:
            seen[chunk["source"]] = {
                "source": chunk["source"],
                "domain": chunk["domain"],
                "jurisdiction": chunk["jurisdiction"],
            }
    return sorted(seen.values(), key=lambda x: x["source"])
