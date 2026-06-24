"""Pytest configuration and shared fixtures."""
import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def sample_params():
    """
    Sample parameters dictionary matching params.json structure.
    Used across multiple test modules.
    """
    return {
        'version': '1.7',
        'goal_weights': {
            'flood_vulnerability': 0.881782946,
            'environmental_quality': 0.787109375,
            'structural_risk': 0.76984127,
            'road_criticality': 0.746062992,
            'wildlife_connectivity': 0.7734375,
            'habitat_quality': 0.7734375,
            'environmental_justice': 0.537698412698412
        },
        'criteria_weights': {
            'fv': {
                'hydraulic_capacity': 0.871900826,
                'flooding_history': 0.818181818181818
            },
            'eq': {
                'erosion': 0.806910569,
                'geomorphic_compatibility': 0.775641026,
                'water_quality': 0.679487179487179
            },
            'sr': {
                'condition': 0.837398374,
                'size': 0.776859504,
                'depth_of_cover': 0.776859504,
                'material': 0.572916667
            },
            'rc': {
                'aadt': 0.618303571428571,
                'distance_to_services': 0.599557522123893,
                'functional_classification': 0.561926606
            },
            'wl': {
                'aop': 0.798728814,
                'special_species': 0.741304347826087
            },
            'hqg': {
                'habitat_quality': 0.717948717948718,
                'wetland_proximity': 0.641592920353982,
                'conservation_status': 0.641592920353982
            }
        },
        'score_maps': {
            'condition': {
                'Poor': 1,
                'Fair': 0.5,
                'Good': 0
            },
            'material': {
                'Steel-Corrugated': 1,
                'Concrete': 0.111,
                'Plastic-Corrugated': 0.028
            },
            'geomorphic_compatibility': {
                'Fully Compatible': 0,
                'Fully Incompatible': 1,
                'Mostly Incompatible': 0.75,
                'Partially Compatible': 0.5,
                'Mostly Compatible': 0.25
            },
            'aop': {
                'Full Passage': 0,
                'Reduced Passage': 0.33,
                'Passage only for Adult Trout': 0.66,
                'No Passage': 1
            }
        },
        'bins': {
            'aadt': [0, 2000, 4000, 6000, 10000, 20000, 1000000],
            'aadt_scores': [0.028, 0.111, 0.250, 0.444, 0.694, 1],
            'size': [0, 7.068583, 12.5, 16, 38.5, 1000000],
            'size_scores': [0, 0.02, 0.184, 0.51, 1],
            'depth_of_cover': [0, 5, 10, 20, 1000000],
            'doc_scores': [0.04, 0.36, 0.64, 1]
        },
        'constants': {
            'cpi': 1.236,
            'bankfull_multiplier': 1.2,
            'base_cost_per_unit': 500
        }
    }


@pytest.fixture
def sample_dataframe():
    """
    Sample dataframe with stream crossing data.
    Contains minimal fields needed for testing various goals.
    """
    return pd.DataFrame({
        # Identifiers
        'SADES_ID': ['SC001', 'SC002', 'SC003', 'SC004'],
        
        # Flood Vulnerability fields
        'HC_2yr': ['Pass', 'Overtop', 'Vulnerable', 'Pass'],
        'HC_10yr': ['Pass', 'Pass', 'Pass', 'Vulnerable'],
        'HC_25yr': ['Pass', 'Pass', 'Pass', 'Pass'],
        'HC_50yr': ['Pass', 'Pass', 'Pass', 'Pass'],
        'HC_100yr': ['Pass', 'Pass', 'Pass', 'Pass'],
        'BlckFlg': [0, 1, 0, 1],
        
        # Structural Risk fields
        'StructCond': ['Good', 'Fair', 'Poor', 'Fair'],
        'UsHwCon': ['Good', 'Fair', 'Poor', 'Good'],
        'DsHwCon': ['Good', 'Good', 'Fair', 'Poor'],
        'StructMat': ['Concrete', 'Steel-Corrugated', 'Concrete', 'Plastic-Corrugated'],
        
        # Road Criticality fields
        'AADT': [1000, 5000, 15000, 500],
        'FUNCT_SYST': [4, 2, 1, 5],
        
        # Environmental Quality fields
        'GC_Score': ['Fully Compatible', 'Mostly Incompatible', 'Partially Compatible', 'Fully Compatible'],
        'Impair': [0, 1, 0, 1],
        
        # Wildlife fields
        'AOP_Score': ['Full Passage', 'No Passage', 'Reduced Passage', 'Full Passage'],
        
        # Habitat fields
        'HQ_WAP': [1, 0, 1, 0],
        
        # Environmental Justice
        'EJScr': [0, 1, 0, 1]
    })


@pytest.fixture
def sample_fv_dataframe():
    """
    Dataframe specifically for flood vulnerability testing.
    """
    return pd.DataFrame({
        'SADES_ID': ['FV001', 'FV002', 'FV003'],
        'HC_2yr': ['Pass', 'Overtop', np.nan],
        'HC_10yr': ['Pass', 'Pass', 'Vulnerable'],
        'HC_25yr': ['Pass', 'Pass', 'Pass'],
        'HC_50yr': ['Pass', 'Pass', 'Pass'],
        'HC_100yr': ['Pass', 'Pass', 'Pass'],
        'BlckFlg': [0, 1, 0]
    })


@pytest.fixture
def sample_scoring_dataframe():
    """
    Simple dataframe for testing scoring utilities.
    """
    return pd.DataFrame({
        'score1': [0.5, 0.8, 0.3, np.nan],
        'score2': [0.6, 0.7, np.nan, 0.9],
        'score3': [np.nan, 0.9, 0.4, 0.2]
    })
