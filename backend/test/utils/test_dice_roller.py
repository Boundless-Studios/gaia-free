"""Tests for dice rolling utilities."""
import pytest
from unittest.mock import patch
from gaia.utils.dice import DiceRoller, DiceParser

class TestDiceRoller:
    """Test dice rolling functionality."""
    
    @pytest.fixture
    def dice_roller(self):
        """Create dice roller instance."""
        
        return DiceRoller()
    
    def test_simple_d20_roll(self, dice_roller):
        """Test rolling a simple d20."""
        result = dice_roller.roll("1d20")
        
        assert result["total"] >= 1
        assert result["total"] <= 20
        assert len(result["rolls"]) == 1
        assert result["expression"] == "1d20"
    
    def test_multiple_dice_roll(self, dice_roller):
        """Test rolling multiple dice."""
        result = dice_roller.roll("3d6")
        
        assert result["total"] >= 3
        assert result["total"] <= 18
        assert len(result["rolls"]) == 3
        assert all(1 <= r <= 6 for r in result["rolls"])
    
    def test_dice_with_modifier(self, dice_roller):
        """Test rolling dice with modifiers."""
        result = dice_roller.roll("1d20+5")
        
        assert result["total"] >= 6  # 1 + 5
        assert result["total"] <= 25  # 20 + 5
        assert result["modifier"] == 5
    
    def test_negative_modifier(self, dice_roller):
        """Test rolling with negative modifier."""
        result = dice_roller.roll("2d6-3")
        
        assert result["total"] >= -1  # 2 - 3
        assert result["total"] <= 9   # 12 - 3
        assert result["modifier"] == -3
    
    def test_advantage_roll(self, dice_roller):
        """Test rolling with advantage."""
        result = dice_roller.roll("1d20", advantage=True)
        
        assert len(result["rolls"]) == 2
        assert result["total"] == max(result["rolls"])
        assert result["advantage"] is True
    
    def test_disadvantage_roll(self, dice_roller):
        """Test rolling with disadvantage."""
        result = dice_roller.roll("1d20", disadvantage=True)
        
        assert len(result["rolls"]) == 2
        assert result["total"] == min(result["rolls"])
        assert result["disadvantage"] is True
    
    def test_complex_expression(self, dice_roller):
        """Test complex dice expressions."""
        result = dice_roller.roll("2d8+1d6+3")
        
        assert result["total"] >= 6   # 2 + 1 + 3
        assert result["total"] <= 27  # 16 + 6 + 3
        assert len(result["rolls"]) == 3
    
    def test_invalid_expression(self, dice_roller):
        """Test invalid dice expressions."""
        with pytest.raises(ValueError):
            dice_roller.roll("invalid")
        
        with pytest.raises(ValueError):
            dice_roller.roll("0d20")
        
        with pytest.raises(ValueError):
            dice_roller.roll("1d0")
    
    def test_critical_detection(self, dice_roller):
        """Test critical hit/miss detection."""
        # Mock to ensure critical
        with patch('random.randint', return_value=20):
            result = dice_roller.roll("1d20")
            assert result["critical"] is True
        
        # Mock to ensure critical fail
        with patch('random.randint', return_value=1):
            result = dice_roller.roll("1d20")
            assert result["critical_fail"] is True
    
    def test_roll_statistics(self, dice_roller):
        """Test roll statistics tracking."""
        # Roll many times to test distribution
        results = []
        for _ in range(100):
            result = dice_roller.roll("1d6")
            results.append(result["total"])
        
        # All results should be in valid range
        assert all(1 <= r <= 6 for r in results)
        
        # Should have reasonable distribution (not all same)
        assert len(set(results)) > 1

class TestDiceParser:
    """Test dice expression parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create dice parser instance."""
        return DiceParser()
    
    def test_parse_simple_expression(self, parser):
        """Test parsing simple dice expressions."""
        result = parser.parse("1d20")
        
        assert result["dice_count"] == 1
        assert result["dice_type"] == 20
        assert result["modifier"] == 0
    
    def test_parse_with_modifier(self, parser):
        """Test parsing expressions with modifiers."""
        result = parser.parse("2d6+3")
        
        assert result["dice_count"] == 2
        assert result["dice_type"] == 6
        assert result["modifier"] == 3
    
    def test_parse_multiple_dice_types(self, parser):
        """Test parsing multiple dice types."""
        result = parser.parse("1d20+2d6+5")
        
        assert len(result["dice_sets"]) == 2
        assert result["dice_sets"][0] == {"count": 1, "type": 20}
        assert result["dice_sets"][1] == {"count": 2, "type": 6}
        assert result["modifier"] == 5
    
    def test_parse_percentile_dice(self, parser):
        """Test parsing percentile dice."""
        result = parser.parse("1d100")
        
        assert result["dice_count"] == 1
        assert result["dice_type"] == 100
    
    def test_parse_damage_types(self, parser):
        """Test parsing with damage type annotations."""
        result = parser.parse("2d6 fire damage")
        
        assert result["dice_count"] == 2
        assert result["dice_type"] == 6
        assert result["damage_type"] == "fire"