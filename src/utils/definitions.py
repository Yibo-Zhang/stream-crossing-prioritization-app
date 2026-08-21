"""Content for the Definitions sheet of the results workbook.

Location in repo: src/utils/definitions.py

The header hover notes carry a one-paragraph description per column, which is
enough to remind a reader what a column is but not enough to explain what an
attribute value means, how a criterion is derived, or how heavily it counts.
This module supplies that longer material for the Definitions sheet.

CRITERIA is the single description of what every criterion measures, which
input fields it reads, the score column it writes, and what leaves it missing.
It is consumed by two places, so the two cannot disagree:

    scripts/excel_report._write_definitions   the Criteria table
    scripts/excel_report._write_run_settings  the criterion weight table

Weights are not held here. They are user-selectable, so they are read from the
params dict of the run in hand and printed only on the Run Settings sheet,
beside the survey default for each one. A weight printed on a static reference
sheet would describe a default rather than the run that produced the numbers.

The prose is taken from Final_scoring_decisions.docx (score calculation
decisions by evaluation criterion) and from the ARPA Stream Crossing
Prioritization Project final report, Section 3 and Table 2.
"""
from utils import report_spec

# --------------------------------------------------------------------------- #
# Goals
# --------------------------------------------------------------------------- #

# Sheet order follows the Spring 2024 UNH Crossing Survey ranking, which is also
# the sheet order of the workbook. goal_key is the key used in
# params['goal_weights']; criteria_key is the key used in
# params['criteria_weights'].
GOALS = [
    ("Flood Vulnerability", "flood_vulnerability", "fv"),
    ("Road Criticality", "road_criticality", "rc"),
    ("Structural Risk", "structural_risk", "sr"),
    ("Wildlife Connectivity", "wildlife_connectivity", "wl"),
    ("Habitat Quality", "habitat_quality", "hqg"),
    ("Environmental Quality", "environmental_quality", "eq"),
    ("Environmental Justice", "environmental_justice", None),
]

# --------------------------------------------------------------------------- #
# Criteria
#
# One entry per criterion, in the order it appears on its goal sheet.
#   goal          sheet the criterion belongs to
#   name          display name, matching the ARPA final report Table 2
#   weight_key    key in params['criteria_weights'][<criteria_key>], or None
#                 where the goal has no criterion split
#   source        input field or fields the criterion is derived from
#   score_col     score column the model writes
#   derivation    how the input becomes a 0 to 1 score
#   missing       what produces a missing value, and what that does
# --------------------------------------------------------------------------- #

CRITERIA = [
    # ---- Flood Vulnerability -------------------------------------------- #
    dict(
        goal="Flood Vulnerability", name="Hydraulic Vulnerability",
        weight_key="hydraulic_capacity",
        source="HC_2yr, HC_10yr, HC_25yr, HC_50yr, HC_100yr",
        score_col="HCScr",
        derivation=(
            "Each return-period field carries a status of Overtop, Vulnerable "
            "or Pass under the NHSCI hydraulic capacity evaluation. Each status "
            "maps to a sub-score and the crossing takes the maximum across the "
            "return periods available, so the worst failure mode governs. "
            "Failure under a more frequent storm scores higher than failure "
            "under a rarer one, and overtopping scores higher than being merely "
            "vulnerable."),
        missing=(
            "Missing only where no hydraulic capacity data exist, for example "
            "at wetland crossings. Pass is a real score of 0, not a gap."),
    ),
    dict(
        goal="Flood Vulnerability", name="Documented History of Flooding",
        weight_key="flooding_history",
        source="BlckFlg", score_col="BlkFScr",
        derivation=(
            "A black-flag point marks documented flooding at or near the "
            "crossing, taken from NH Town Hazard Mitigation Plans. Each point "
            "is the centroid of a flooded-area polygon snapped to the nearest "
            "stream-road crossing within a 500 ft radius. A flag scores 1."),
        missing=(
            "An unflagged crossing scores missing, not 0. Absence of a record "
            "means the flooding was not documented, which is not the same as an "
            "absence of flood risk. Scoring it 0 would dilute the score of a "
            "crossing with a severe hydraulic capacity failure but no recorded "
            "washout."),
    ),

    # ---- Road Criticality ------------------------------------------------ #
    dict(
        goal="Road Criticality", name="Annual Average Daily Traffic",
        weight_key="aadt",
        source="AADT", score_col="AADTScr",
        derivation=(
            "Average annual daily traffic on the road carried by the crossing, "
            "from the NHDOT road inventory, placed in bins. Higher traffic "
            "gives a higher score."),
        missing="Missing where the road inventory records no AADT.",
    ),
    dict(
        goal="Road Criticality", name="Distance to Important Services",
        weight_key="distance_to_services",
        source="Dst_Hsptl, Dst_EMS, Dst_LawEn, Dst_Fire", score_col="DstIMPScr",
        derivation=(
            "MinDstImP is the shortest of the distances to the nearest "
            "hospital, emergency medical service, law enforcement and fire "
            "station. A closer crossing scores higher, because a closure there "
            "lengthens an emergency response."),
        missing=(
            "Missing where no distance is recorded. A crossing beyond 2 units "
            "scores a real 0, so a distant crossing and an unmeasured one are "
            "kept apart."),
    ),
    dict(
        goal="Road Criticality", name="Functional Classification",
        weight_key="functional_classification",
        source="FUNCT_SYST", score_col="FncSysScr",
        derivation=(
            "FHWA functional class of the road carried by the crossing. "
            "Higher-order roads carry more traffic and serve wider network "
            "mobility, so they score higher."),
        missing="Missing where the road inventory records no class.",
    ),

    # ---- Structural Risk ------------------------------------------------- #
    dict(
        goal="Structural Risk", name="Structural Condition",
        weight_key="condition",
        source="StructCond, UsHwCon, DsHwCon", score_col="CondScr",
        derivation=(
            "Structure, inlet headwall and outlet headwall condition are each "
            "mapped Poor 1, Fair 0.5, Good 0, then combined as 0.5 structure "
            "plus 0.3 inlet plus 0.2 outlet. Where only two are recorded the "
            "two weights are renormalised to sum to one, for example structure "
            "and inlet use 0.5/0.8 and 0.3/0.8. Where only one is recorded, "
            "that value is used directly."),
        missing="Missing only where none of the three condition fields is recorded.",
    ),
    dict(
        goal="Structural Risk", name="Size",
        weight_key="size",
        source="UsWidth, UsOpenHght, StructType", score_col="SizeScr",
        derivation=(
            "Upstream opening area, computed as (pi/4) x UsWidth squared for a "
            "round culvert, using pi = 3.14, and as UsWidth x UsOpenHght for "
            "every other shape, then placed in bins. A larger opening scores "
            "higher. The first break of 7.07 sq ft is the opening area of a "
            "3 ft diameter round culvert, the minimum for a meaningful passage "
            "opening."),
        missing=(
            "A computed area of 0 is treated as missing, since a zero opening "
            "is physically infeasible and indicates absent input data. Size is "
            "also dropped from the goal where Structural Condition is 0 (Good) "
            "or missing."),
    ),
    dict(
        goal="Structural Risk", name="Material",
        weight_key="material",
        source="StructMat", score_col="MatScr",
        derivation=(
            "Construction material, ranked by durability and expected service "
            "life, consistent with the shorter service life and greater "
            "corrosion susceptibility of metal culverts relative to concrete "
            "and plastic."),
        missing="Missing where no material is recorded.",
    ),

    # ---- Wildlife Connectivity ------------------------------------------- #
    dict(
        goal="Wildlife Connectivity", name="Aquatic Organism Passage",
        weight_key="aop",
        source="AOP_Score", score_col="AOPScr",
        derivation=(
            "The NHSCI aquatic organism passage rating, describing whether fish "
            "and other aquatic organisms can move through or beneath the "
            "structure. A full barrier scores 1."),
        missing=(
            "Missing where the crossing could not be scored for passage, for "
            "example a private or unsurveyable crossing. Full Passage is a real "
            "score of 0."),
    ),
    dict(
        goal="Wildlife Connectivity", name="Special Species Presence",
        weight_key="special_species",
        source="Sp_Sp_FG", score_col="SpSpScr",
        derivation=(
            "Confirmed presence of a priority fish species from the NH Fish and "
            "Game dataset covering American Brook Lamprey, American Shad, River "
            "Herring, Sea Lamprey, wild Eastern Brook Trout and Red-fin "
            "Pickerel. Presence scores 1. Special species are counted only "
            "where the passage score is above 0, so a crossing that already "
            "passes fish freely is not raised further."),
        missing=(
            "No recorded presence scores missing, not 0, so the criterion acts "
            "as a conditional aggravating factor rather than a penalty on "
            "crossings that simply have no species survey."),
    ),
    dict(
        goal="Wildlife Connectivity", name="Wildlife Corridor",
        weight_key="terrestrial_organism_passage",
        source="WlCo", score_col="WlCoScr",
        derivation=(
            "Whether the crossing falls inside a mapped corridor in the NH Fish "
            "and Game statewide wildlife connectivity model, which maps the "
            "corridors linking the state's highest-ranked core habitats. "
            "Assigned by point-in-polygon containment; a crossing on a polygon "
            "boundary counts as inside."),
        missing=(
            "Every crossing is evaluated against the same statewide layer, so a "
            "0 is a determined absence rather than a gap. Added in v1.2."),
    ),

    # ---- Habitat Quality -------------------------------------------------- #
    dict(
        goal="Habitat Quality", name="Habitat Condition Tier",
        weight_key="habitat_condition_tier",
        source="HQ_WAP, WAP_TIER", score_col="HCTScr",
        derivation=(
            "Habitat condition tier of the highest-ranked habitat polygon "
            "within 100 ft, from the NH Fish and Game dataset The Highest "
            "Ranked Wildlife Habitat by Ecological Condition (2020 NH Wildlife "
            "Action Plan). Tier 1, highest ranked in the state, scores 1.0; "
            "Tier 2, highest ranked in the biological region, scores 0.66; "
            "Tier 3, supporting landscape, scores 0.33."),
        missing=(
            "A crossing outside any ranked tier scores a real 0, a determined "
            "absence. Renamed from 'habitat quality' in v1.2 to remove the "
            "collision with the goal name; the score column HQScr became "
            "HCTScr."),
    ),
    dict(
        goal="Habitat Quality", name="Wetland Proximity",
        weight_key="wetland_proximity",
        source="Wetlnd", score_col="WtlndScr",
        derivation=(
            "Whether a wetland lies within 100 ft of the crossing, from the "
            "statewide National Wetlands Inventory layer, excluding Riverine "
            "wetlands."),
        missing=(
            "Every crossing is evaluated against the same layer, so a 0 means "
            "no qualifying wetland within 100 ft, not missing data."),
    ),
    dict(
        goal="Habitat Quality", name="Conservation Status",
        weight_key="conservation_status",
        source="ConsvStat", score_col="CnsvStScr",
        derivation=(
            "Whether conserved land lies within 100 ft of the crossing, from "
            "the GRANIT Conservation/Public Lands layer maintained by the NH "
            "GRANIT geospatial data clearinghouse."),
        missing=(
            "Every crossing is evaluated against the same layer, so a 0 means "
            "no conserved land within 100 ft, not missing data."),
    ),

    # ---- Environmental Quality -------------------------------------------- #
    dict(
        goal="Environmental Quality", name="Erosion",
        weight_key="erosion",
        source=("UsUndermin, DsUndermin, UsObstruct, OutScour, StructSed, "
                "UsBankEros, DsBankEros, UsBankArmo, DsBankArmo"),
        score_col="ErosScr",
        derivation=(
            "The arithmetic mean of up to nine field-observed components: "
            "upstream and downstream undermining, opening obstruction, outlet "
            "scour, sediment fill, upstream and downstream bank erosion, and "
            "upstream and downstream bank armouring. The mean skips missing "
            "components, so only what was recorded contributes."),
        missing=(
            "Missing only where none of the nine components was recorded. Note "
            "that the two undermining fields collapse a multi-level inventory "
            "(footers, culvert, wing walls, abutments and combinations) to a "
            "single value of 1, so severity gradation is lost."),
    ),
    dict(
        goal="Environmental Quality", name="Geomorphic Compatibility",
        weight_key="geomorphic_compatibility",
        source="GC_Score", score_col="GCScr",
        derivation=(
            "The NHSCI geomorphic compatibility rating: how well the structure "
            "fits the channel, whether it is aligned with and spans the "
            "channel and matches its slope, and whether it passes sediment "
            "without upstream deposition that raises velocity and the risk of "
            "failure during storms."),
        missing=(
            "Missing where the crossing could not be rated, for example a "
            "wetland, tidal or surface-water crossing. Fully Compatible is a "
            "real score of 0."),
    ),
    dict(
        goal="Environmental Quality", name="Water Quality Impairment",
        weight_key="water_quality",
        source="Impair", score_col="WQIScr",
        derivation=(
            "Whether the crossing sits on an impaired water body. Built by "
            "filtering the NHDES Surface Water Quality Assessment to "
            "integrated-reporting categories 4 and 5, the impaired waters "
            "making up the state 303(d)/305(b) list, for the eight target "
            "nutrient and eutrophication parameters."),
        missing=(
            "A crossing that is not flagged corresponds to a water body that "
            "does not match the filter, for example category 2 or 3, and scores "
            "a real 0. Water quality enters the goal only where the erosion "
            "score is present and above 0."),
    ),
    dict(
        goal="Environmental Quality", name="Watershed Water Quality Impairment",
        weight_key="water_quality",
        source="WWQI", score_col="WWQIScr",
        derivation=(
            "Whether the crossing falls inside a HUC12-clipped impaired "
            "watershed. Built by filtering the same assessment to lakes and "
            "impoundments (AUID prefixes NHLAK and NHIMP), categories 4 and 5, "
            "and the eight target parameters, then flagging crossings inside "
            "the impaired watersheds clipped to intersecting HUC12 "
            "sub-watersheds."),
        missing=(
            "As for Water Quality Impairment: a 0 is a determined absence, and "
            "the criterion enters the goal only where the erosion score is "
            "present and above 0. Added in v1.2."),
    ),

    # ---- Environmental Justice -------------------------------------------- #
    dict(
        goal="Environmental Justice", name="Climate and Economic Justice Screening Tool",
        weight_key=None,
        source="EJScr", score_col="EJScr",
        derivation=(
            "Whether the crossing lies within a disadvantaged community "
            "identified by the Climate and Economic Justice Screening Tool "
            "(CEJST), developed by the Council on Environmental Quality, which "
            "identifies communities carrying significant burdens across eight "
            "categories: climate change, energy, health, housing, legacy "
            "pollution, transportation, water and wastewater, and workforce "
            "development. Assigned by point-in-polygon containment."),
        missing=(
            "Never missing. This goal has a single criterion, so a crossing is "
            "either inside a disadvantaged community or it is not; a 0 is a "
            "determined outcome rather than absent data."),
    ),
]
