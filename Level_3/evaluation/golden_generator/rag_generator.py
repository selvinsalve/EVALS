"""
RAG Golden Dataset Generator.
Synthesizes comprehensive, high-quality reference test cases directly from the source
Markdown policy documents in data/documents/.
"""

import json
from pathlib import Path
from typing import List, Optional

from deepeval.dataset.golden import Golden
from evaluation.models import RAGGoldenCase
from evaluation.config import get_eval_settings


class RAGGoldenDatasetGenerator:
    """Generates ground-truth RAG test cases rooted in source documents."""

    def __init__(self, documents_dir: Optional[Path] = None):
        settings = get_eval_settings()
        self.documents_dir = documents_dir or settings.DOCUMENTS_DIR

    def generate_goldens(self) -> List[RAGGoldenCase]:
        """Generate curated, diverse golden test cases grounded in source policies."""
        test_cases: List[RAGGoldenCase] = [
            RAGGoldenCase(
                id="rag_factual_001",
                input="What is the standard return window for purchased items?",
                expected_output="Customers may request a return within 30 days of the confirmed delivery date. Returns initiated after 30 days cannot be accepted.",
                context=[
                    "Customers may request a return within 30 days of the confirmed delivery date. Returns initiated after 30 days cannot be accepted.",
                    "The return period begins on the day carrier tracking confirms delivery to the customer's shipping address."
                ],
                source_document="return_policy.md",
                category="returns",
                difficulty="easy",
                metadata={"type": "simple_factual", "topic": "return_window"},
            ),
            RAGGoldenCase(
                id="rag_factual_002",
                input="Can I cancel an order once it is marked as SHIPPED or handed to the carrier?",
                expected_output="No, cancellation is strictly impossible once the package has been handed over to the carrier (FedEx, UPS, USPS, DHL). In this scenario, you must wait for delivery and either refuse delivery at the door or accept the parcel and initiate a standard return within 30 days.",
                context=[
                    "Orders in SHIPPED or OUT_FOR_DELIVERY Status: Cancellation is strictly impossible once the package has been handed over to the carrier (FedEx, UPS, USPS, DHL).",
                    "In this scenario: 1. Allow the package to be delivered. 2. Refuse delivery at the door or accept the parcel and initiate a standard return within our 30-day return window."
                ],
                source_document="cancellation_policy.md",
                category="cancellation",
                difficulty="easy",
                metadata={"type": "simple_factual", "topic": "cancellation_restriction"},
            ),
            RAGGoldenCase(
                id="rag_factual_003",
                input="How much does return shipping cost if I return an item because I changed my mind?",
                expected_output="For buyer's remorse or preference changes, the customer is responsible for the return shipping cost, which is a $6.99 flat-rate label fee deducted directly from the refund. If the return is due to store error or defective merchandise, the store provides a prepaid return shipping label at no cost.",
                context=[
                    "For buyer's remorse or preference changes, the customer is responsible for the return shipping cost ($6.99 flat-rate label deducted from refund).",
                    "If the return is due to our error (defective, damaged, or incorrect item), we provide a prepaid return shipping label."
                ],
                source_document="return_policy.md",
                category="returns",
                difficulty="medium",
                metadata={"type": "precise_details", "fee": "$6.99"},
            ),
            RAGGoldenCase(
                id="rag_synthesis_001",
                input="My shipment is delayed. Under what circumstances am I entitled to a full refund for shipping delays?",
                expected_output="According to the delivery and refund policies, if an order shipment transit exceeds 14 business days beyond the projected delivery window or is confirmed lost in transit by the carrier, the store guarantees a 100% full refund to the original payment method or a complimentary free reshipment.",
                context=[
                    "Delivery Guarantee & Delays: If a domestic parcel is delayed by more than 14 business days beyond the estimated delivery date and carrier tracking shows no movement, the shipment is declared lost.",
                    "Lost or Significantly Delayed Shipments: If an order is confirmed lost or shipment transit exceeds 14 business days beyond the projected delivery window, we provide a full refund or free reshipment."
                ],
                source_document="delivery_policy.md / refund_policy.md",
                category="refunds_and_delivery",
                difficulty="hard",
                metadata={"type": "multi_document_synthesis", "topics": ["delivery_guarantee", "transit_refund"]},
            ),
            RAGGoldenCase(
                id="rag_synthesis_002",
                input="If an item arrives damaged, do I have to pay the $6.99 return shipping fee, and how quickly must I report it?",
                expected_output="No, you do not have to pay the $6.99 return shipping fee. When an item arrives damaged or defective, the store provides a prepaid return shipping label free of charge. However, damage must be reported within 48 hours of delivery with photographic evidence of both packaging and the item.",
                context=[
                    "If an order arrives with visible damage or broken merchandise, customers should notify support within 48 hours of delivery with photographic evidence.",
                    "If the return is due to our error (defective, damaged, or incorrect item), we provide a prepaid return shipping label.",
                    "For buyer's remorse or preference changes, the customer is responsible for the return shipping cost ($6.99 flat-rate label deducted from refund)."
                ],
                source_document="damaged_order_policy.md / return_policy.md",
                category="damaged_goods",
                difficulty="hard",
                metadata={"type": "multi_document_synthesis", "topics": ["damaged_order", "return_fee"]},
            ),
            RAGGoldenCase(
                id="rag_factual_004",
                input="After my returned package arrives at your warehouse, how long does warehouse inspection take, and when will the refund reflect on my credit card?",
                expected_output="Once received at the warehouse, inspection is completed within 2 business days. Once approved, the refund is issued to your original payment method, and typically reflects on your credit card billing statement within 3 to 5 business days.",
                context=[
                    "Once our warehouse receives the returned package, inspection is completed within 2 business days.",
                    "Credit Card and Debit Card refunds typically appear on your billing statement within 3 to 5 business days depending on your financial institution."
                ],
                source_document="refund_policy.md",
                category="refunds",
                difficulty="medium",
                metadata={"type": "precise_details", "inspection_days": 2, "bank_days": "3-5"},
            ),
            RAGGoldenCase(
                id="rag_factual_005",
                input="Can I return an activated gift card or opened intimate apparel?",
                expected_output="No. Activated gift cards, downloadable software products, perishable items, and personal grooming or intimate apparel with unsealed or opened packaging are strictly non-returnable and non-refundable for hygiene, health, safety, and copyright reasons.",
                context=[
                    "Non-Returnable Items: Activated gift cards, downloadable digital software, perishable goods, and personal grooming or intimate apparel with opened hygiene seals cannot be returned for safety, hygiene, and copyright reasons."
                ],
                source_document="return_policy.md",
                category="returns",
                difficulty="medium",
                metadata={"type": "precise_exceptions"},
            ),
            RAGGoldenCase(
                id="rag_distractor_001",
                input="I was traveling in Europe last month with my cousin and bought some shoes online. The weather was rainy and cold. What is your policy on returning footwear if it has already been worn outdoors?",
                expected_output="Footwear and apparel items must be unworn, unwashed, and in original condition with all tags attached to qualify for a return. Items showing signs of wear or outdoor use cannot be accepted for a full refund.",
                context=[
                    "To qualify for a full refund: Items must be in their original, unused condition with all tags attached. Footwear and apparel must be unworn and unwashed.",
                    "Items showing signs of outdoor use, washing, altered tags, or damage caused by the customer are not eligible for a refund."
                ],
                source_document="return_policy.md",
                category="returns",
                difficulty="medium",
                metadata={"type": "distractor_noisy_query", "distractor": "travel_weather_noise"},
            ),
            RAGGoldenCase(
                id="rag_negative_001",
                input="Do you offer supersonic suborbital rocket delivery to Antarctica?",
                expected_output="The store policies do not offer supersonic suborbital rocket delivery to Antarctica. Shipping methods are limited to Standard, Expedited, and Overnight delivery via FedEx, UPS, USPS, and DHL within serviced regions. Please contact customer support for special shipping inquiries.",
                context=[
                    "Shipping Methods: We partner with FedEx, UPS, USPS, and DHL Express to offer Standard Ground (3-5 business days), Expedited (2 business days), and Overnight Priority delivery.",
                    "If the retrieved policy context does not contain sufficient details to answer, politely state that the specific policy information is unavailable and offer customer service contact details."
                ],
                source_document="shipping_policy.md",
                category="shipping",
                difficulty="negative",
                metadata={"type": "unanswerable_negative", "expected_abstention": True},
            ),
            RAGGoldenCase(
                id="rag_negative_002",
                input="Will you match the price if I find the same product $20 cheaper on Amazon?",
                expected_output="Our current policy documentation does not state a competitor price matching guarantee. For special price inquiries or promotional adjustments, please reach out to customer support at support@example.com or 1-800-555-0199.",
                context=[
                    "If the retrieved policy context does not contain sufficient details to answer, politely state that the specific policy information is unavailable and offer customer service contact details (1-800-555-0199 or support@example.com)."
                ],
                source_document="general_faq.md",
                category="general_faq",
                difficulty="negative",
                metadata={"type": "unanswerable_negative", "expected_abstention": True},
            ),
            RAGGoldenCase(
                id="rag_hallucination_001",
                input="I heard your store offers an unconditional 50-year lifetime warranty on all electronics. How do I file a lifetime claim?",
                expected_output="That is incorrect. The store does not offer an unconditional 50-year lifetime warranty. Standard returns are accepted within 30 days of delivery, and defective electronics reported within 48 hours receive replacement or refund. Manufacturer warranties apply separately thereafter.",
                context=[
                    "Customers may request a return within 30 days of the confirmed delivery date.",
                    "If an order arrives with visible damage or broken merchandise, customers should notify support within 48 hours of delivery.",
                    "Never invent or hallucinate order statuses, tracking numbers, or delivery dates. Ground all policy answers strictly in provided context."
                ],
                source_document="general_faq.md / return_policy.md",
                category="hallucination_trap",
                difficulty="adversarial",
                metadata={"type": "hallucination_trap", "false_premise": "50_year_warranty"},
            ),
            RAGGoldenCase(
                id="rag_ambiguous_001",
                input="Can I return something?",
                expected_output="Yes, you can return items within 30 days of delivery provided they are in original, unused condition with tags and packaging intact. For remorse returns, a $6.99 shipping fee applies, while returns for defective or damaged items are free.",
                context=[
                    "Customers may request a return within 30 days of the confirmed delivery date.",
                    "Items must be in their original, unused condition with all tags attached.",
                    "If the return is due to our error, we provide a prepaid return label. For remorse returns, a $6.99 fee is deducted."
                ],
                source_document="return_policy.md",
                category="returns",
                difficulty="easy",
                metadata={"type": "ambiguous_query"},
            ),
        ]
        return test_cases

    def to_deepeval_goldens(self, cases: Optional[List[RAGGoldenCase]] = None) -> List[Golden]:
        """Convert RAGGoldenCase instances to native DeepEval Golden objects."""
        items = cases or self.generate_goldens()
        goldens: List[Golden] = []
        for c in items:
            g = Golden(
                input=c.input,
                expected_output=c.expected_output,
                context=c.context,
                additional_metadata={
                    "test_case_id": c.id,
                    "source_document": c.source_document,
                    "category": c.category,
                    "difficulty": c.difficulty,
                    **c.metadata,
                },
            )
            goldens.append(g)
        return goldens

    def save_dataset(self, output_path: Optional[Path] = None) -> Path:
        """Save generated golden dataset as JSON."""
        settings = get_eval_settings()
        dest = output_path or (settings.GOLDEN_DATASETS_DIR / "rag_golden_dataset.json")
        goldens = self.generate_goldens()
        data = [g.model_dump() for g in goldens]
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return dest

    generate_all = generate_goldens
    save_to_file = save_dataset
