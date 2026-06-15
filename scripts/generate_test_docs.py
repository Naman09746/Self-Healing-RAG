from fpdf import FPDF
import os

class TestDocGenerator:
    def __init__(self, output_dir="test_data"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def create_pdf(self, filename, title, content):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, title, ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Helvetica", size=12)
        
        for section, text in content.items():
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 10, section, ln=True)
            pdf.set_font("Helvetica", size=11)
            pdf.multi_cell(0, 8, text)
            pdf.ln(5)
            
        path = os.path.join(self.output_dir, filename)
        pdf.output(path)
        print(f"Generated: {path}")

    def generate_all(self):
        # 1. Project Omega Specification (Technical Complexity)
        self.create_pdf(
            "project_omega_spec.pdf",
            "Project Omega: Distributed AI Orchestration",
            {
                "1. Executive Overview": "Project Omega is a Tier-1 autonomous orchestration layer designed for heterogeneous compute clusters. It utilizes a Non-Euclidean Memory Mesh to manage state across 10,000+ edge nodes.",
                "2. System Architecture": "The core consists of the 'Aether Kernel' which handles sub-millisecond task dispatching. It is cross-linked with the 'Chronos Ledger' for immutable event sequencing. Security is enforced via the 'Hydra Protocol', a multi-sig biometric validation layer.",
                "3. Inter-agent Communication": "Agents communicate using the 'Singularity Bus'. When Agent-01 (Primary) initiates a 'Neural Handshake', Agent-07 (Watcher) must validate the checksum against the 'Deep-State Vault'. If mismatch occurs, 'Protocol-99' is triggered, resulting in immediate cluster isolation.",
                "4. Technical Requirements": "Minimum latency: 0.4ms. Throughput: 1.2M OPS. Redundancy: 3x mirror via 'Shadow-Node' synchronization."
            }
        )

        # 2. Q4 Strategic Intelligence Report (Interconnected Entities)
        self.create_pdf(
            "q4_strategic_intelligence.pdf",
            "Q4 2025: Global Market Intelligence Report",
            {
                "1. Market Dynamics": "The acquisition of 'Quantum-Leap Systems' by 'Nexus-Global Corp' has disrupted the silicon-photonics market. This directly impacts the supply chain of 'Neo-Tech Industries', our primary partner.",
                "2. Competitor Analysis": "Competitor 'Astra AI' has leaked their 'Project Nova' roadmap. It shows a clear intent to move into the 'Synthetic Biology' space, leveraging their proprietary 'Helix-V' transformer model.",
                "3. Risk Factors": "The 'Turing Accord' re-negotiation in Geneva poses a regulatory threat to all companies using 'Unsupervised Feedback Loops'. 'Nexus-Global Corp' is lobbying against Section 4.2 which mandates 'Human-in-the-Loop' for all Tier-3 decisions.",
                "4. Strategic Recommendations": "Pivot R&D towards 'Zero-Knowledge Proofs' to bypass the 'Turing Accord' constraints. Strengthen alliance with 'Neo-Tech Industries' to secure exclusive photonics hardware."
            }
        )

        # 3. Incident Post-Mortem: Cluster Zero (Troubleshooting/Graph Logic)
        self.create_pdf(
            "incident_post_mortem_cluster_zero.pdf",
            "Incident Post-Mortem: Cluster Zero Cascading Failure",
            {
                "1. Incident Summary": "At 14:02 UTC, Cluster Zero experienced a total blackout. This was initiated by a 'Phantom Leak' in the 'Vortex-7' cooling subsystem, which caused the 'Mainframe-Alpha' thermal sensors to provide false-positive readings.",
                "2. Root Cause Analysis": "The 'Vortex-7' leak was traced back to a faulty valve supplied by 'Valv-Co', a subsidiary of 'Neo-Tech Industries'. The false-positive from 'Mainframe-Alpha' caused the 'Sentinel Agent' to shut down the 'Power-Grid-Gamma', thinking there was a fire.",
                "3. Cascading Effects": "Shutting down 'Power-Grid-Gamma' severed the link to the 'Storage-Delta' array. This resulted in data corruption in the 'Customer-Insight-DB'. Ironically, the 'Healer-Agent' tried to fix the DB using backup data from 'Archive-Sigma', which was already corrupted by the thermal spike.",
                "4. Remediation Plan": "Replace all 'Valv-Co' hardware. Update 'Sentinel Agent' logic to cross-verify thermal readings with 'Auxiliary-Sensor-Beta'. Relocate 'Archive-Sigma' to a different geographic zone."
            }
        )

if __name__ == "__main__":
    gen = TestDocGenerator()
    gen.generate_all()
