"""VAT calculation service for German Gastronomy."""

from __future__ import annotations
from typing import Dict

class TaxService:
    """
    Handles German VAT (MwSt) logic for Gastronomy.
    
    In Germany:
    - 19% (Standard Rate): In-house consumption and all beverages.
    - 7% (Reduced Rate): Take-away food.
    """

    @staticmethod
    def get_vat_rate(order_type: str, category: str) -> float:
        """
        Determines the correct German VAT rate (7.0 or 19.0).
        
        Args:
            order_type: 'in_house' or 'take_away'
            category: Product category (e.g., 'Food', 'Drinks')
            
        Returns:
            The applicable VAT rate as a float.
        """
        # Beverages are always 19% in Germany
        if category.lower() in ["drinks", "beverages", "alcohol", "softdrinks"]:
            return 19.0
        
        # Food is 19% if eaten in the restaurant, 7% if taken away
        if order_type == "in_house":
            return 19.0
            
        return 7.0

    @staticmethod
    def calculate_tax_from_gross(gross_amount: float, vat_rate: float) -> Dict[str, float]:
        """
        Calculates net and tax amounts from a gross price.
        Most German POS systems display gross prices to customers.
        """
        # net = gross / (1 + rate/100)
        net_amount = gross_amount / (1 + (vat_rate / 100))
        vat_amount = gross_amount - net_amount
        
        return {
            "gross": round(gross_amount, 2),
            "net": round(net_amount, 2),
            "vat_amount": round(vat_amount, 2),
            "vat_rate": vat_rate
        }
