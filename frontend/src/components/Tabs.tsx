export type Tab = { key: string; label: string };

export function Tabs({
  tabs,
  activeKey,
  onChange,
}: {
  tabs: Tab[];
  activeKey: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-2 border-b border-gray-200">
      {tabs.map((t) => {
        const active = t.key === activeKey;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={`-mb-px px-3 py-2 text-sm font-medium ${
              active
                ? "border-b-2 border-black text-black"
                : "text-gray-500 hover:text-black"
            }`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
