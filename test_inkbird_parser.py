#!/usr/bin/env python3
"""
Simple test script for Inkbird IBS-M2 data parser
This tests the core parsing functionality without requiring Home Assistant
"""

import sys
import os
import base64
import struct

# Add the custom_components path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components', 'xtend_tuya'))

# Mock the Home Assistant constants since we're testing outside HA
class MockUnitOfTemperature:
    CELSIUS = "°C"
    FAHRENHEIT = "°F"

class MockLogger:
    def debug(self, msg, *args):
        print(f"DEBUG: {msg % args if args else msg}")
    def info(self, msg, *args):
        print(f"INFO: {msg % args if args else msg}")
    def warning(self, msg, *args):
        print(f"WARNING: {msg % args if args else msg}")
    def error(self, msg, *args):
        print(f"ERROR: {msg % args if args else msg}")

# Patch the imports before importing our module
import sys
sys.modules['homeassistant.const'] = type('MockModule', (), {'UnitOfTemperature': MockUnitOfTemperature})()
sys.modules['custom_components.xtend_tuya.const'] = type('MockModule', (), {'LOGGER': MockLogger()})()

# Now import our parser
from inkbird_data_parser import InkbirdB64TypeData

def test_parser_with_sample_data():
    """Test the parser with the actual device data from the JSON file"""
    
    # Sample data from the device debug JSON
    test_cases = [
        {
            "name": "Channel 0 (Active) - from logs",
            "data": "AQUBjQEAEA4AZA==",  # From actual logs
            "expected_temp_range": (20, 40),  # Should be around 30°C based on raw data
            "expected_humidity_range": (0, 100),
        },
        {
            "name": "Channel 0 (Original test data)",
            "data": "AXoBhwEAEA4AZA==",  # From ch_0 in the JSON
            "expected_temp_range": (20, 40),  # Should be around 30°C based on raw data
            "expected_humidity_range": (0, 100),
        },
        {
            "name": "Channel 1 (Inactive)",
            "data": "CPUA////////ZA==",  # From ch_1 in the JSON  
            "expected_temp_range": None,  # This might be invalid data
            "expected_humidity_range": None,
        },
        {
            "name": "Channel 2 (Inactive)", 
            "data": "CPQA////////ZA==",  # From ch_2 in the JSON
            "expected_temp_range": None,  # This might be invalid data
            "expected_humidity_range": None,
        }
    ]
    
    print("🧪 Testing Inkbird IBS-M2 Data Parser")
    print("=" * 50)
    
    for test_case in test_cases:
        print(f"\n📊 Testing {test_case['name']}")
        print(f"   Raw data: {test_case['data']}")
        
        try:
            # Parse the data
            parsed = InkbirdB64TypeData.from_raw(test_case['data'])
            
            print(f"   ✅ Parsing successful!")
            print(f"   🌡️  Temperature: {parsed.temperature} {parsed.temperature_unit}")
            print(f"   💧 Humidity: {parsed.humidity}%")
            print(f"   🔋 Battery: {parsed.battery}%")
            
            # Validate ranges if specified
            if test_case['expected_temp_range'] and parsed.temperature is not None:
                temp_min, temp_max = test_case['expected_temp_range']
                if temp_min <= parsed.temperature <= temp_max:
                    print(f"   ✅ Temperature in expected range ({temp_min}-{temp_max})")
                else:
                    print(f"   ⚠️  Temperature outside expected range ({temp_min}-{temp_max})")
            
            if test_case['expected_humidity_range'] and parsed.humidity is not None:
                hum_min, hum_max = test_case['expected_humidity_range']
                if hum_min <= parsed.humidity <= hum_max:
                    print(f"   ✅ Humidity in expected range ({hum_min}-{hum_max})")
                else:
                    print(f"   ⚠️  Humidity outside expected range ({hum_min}-{hum_max})")
                    
        except Exception as e:
            print(f"   ❌ Parsing failed: {e}")

def test_parser_edge_cases():
    """Test edge cases and invalid data"""
    
    print(f"\n🔬 Testing Edge Cases")
    print("=" * 30)
    
    edge_cases = [
        {
            "name": "Empty string",
            "data": "",
        },
        {
            "name": "Invalid base64",
            "data": "invalid_base64_data",
        },
        {
            "name": "Too short data",
            "data": "QWE=",  # Valid base64 but too short
        },
        {
            "name": "Fahrenheit data",
            "data": "FXoBhwEAEA4AZA==",  # Same as channel 0 but with 'F' prefix
        }
    ]
    
    for test_case in edge_cases:
        print(f"\n📋 Testing {test_case['name']}")
        print(f"   Raw data: {test_case['data']}")
        
        try:
            parsed = InkbirdB64TypeData.from_raw(test_case['data'])
            print(f"   ✅ Parsing successful!")
            print(f"   🌡️  Temperature: {parsed.temperature} {parsed.temperature_unit}")
            print(f"   💧 Humidity: {parsed.humidity}%")
            print(f"   🔋 Battery: {parsed.battery}%")
        except Exception as e:
            print(f"   ⚠️  Expected failure: {e}")

def decode_raw_bytes():
    """Manually decode the bytes to understand the data structure"""
    
    print(f"\n🔍 Raw Byte Analysis")
    print("=" * 30)
    
    data = "AXoBhwEAEA4AZA=="
    print(f"Analyzing: {data}")
    
    try:
        decoded = base64.b64decode(data)
        print(f"Decoded bytes: {decoded}")
        print(f"Byte length: {len(decoded)}")
        print(f"Hex representation: {decoded.hex()}")
        
        if len(decoded) >= 11:
            # Try to unpack according to our format
            temp_raw, humidity_raw, unknown, battery = struct.unpack("<hHIb", decoded[1:11])
            print(f"\nStruct unpacking (skipping first byte):")
            print(f"  Temperature raw: {temp_raw} -> {temp_raw / 10.0}")
            print(f"  Humidity raw: {humidity_raw} -> {humidity_raw / 10.0}")
            print(f"  Unknown field: {unknown}")
            print(f"  Battery: {battery}")
            
    except Exception as e:
        print(f"Analysis failed: {e}")

if __name__ == "__main__":
    test_parser_with_sample_data()
    test_parser_edge_cases()
    decode_raw_bytes()
    
    print(f"\n🎉 Testing complete!")
