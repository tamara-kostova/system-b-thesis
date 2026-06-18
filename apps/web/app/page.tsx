import Link from "next/link";

const cards = [
  {
    href: "/datasets",
    title: "Browse Datasets",
    description: "Explore available OMOP health datasets and their coverage.",
  },
  {
    href: "/concepts",
    title: "Search Concepts",
    description: "Search OMOP vocabulary concepts and view suppressed patient counts.",
  },
  {
    href: "/apply",
    title: "Apply for Access",
    description: "Submit a data access application under EHDS Article 67.",
  },
  {
    href: "/register",
    title: "Public Register",
    description: "View all currently granted data access permits (EHDS Article 68).",
  },
];

export default function Home() {
  return (
    <div className="max-w-5xl">
      <div className="bg-blue-700 rounded-xl px-8 py-10 mb-10 text-white">
        <p className="text-xs font-semibold uppercase tracking-widest text-blue-200 mb-2">
          EHDS Chapter IV · OMOP CDM v5.4
        </p>
        <h1 className="text-3xl font-bold mb-3">SecureHealth Data Access Platform</h1>
        <p className="text-blue-100 max-w-xl text-sm leading-relaxed">
          A reference implementation of an EHDS-compliant platform for secondary use of health
          data - with permit-scoped LLM assistance, secure processing environments, and an
          output disclosure airlock.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {cards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="block bg-white border border-gray-200 border-t-4 border-t-blue-500 rounded-lg p-5 shadow-sm hover:shadow-md transition-all group"
          >
            <h2 className="text-base font-medium text-gray-900 group-hover:text-blue-700 mb-1 transition-colors">{card.title}</h2>
            <p className="text-sm text-gray-500">{card.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
