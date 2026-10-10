"use client";
import { motion } from "framer-motion";
import { ArrowRight, Brain, FileUp, Sparkles, UserCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { Card, Field } from "@/components/ui/Primitives";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";

const EMPTY = { reference: "", importer: "", exporter: "", origin: "", destination: "", port: "", carrier: "", container_number: "", product_description: "" };
type Form = typeof EMPTY;

const DEMO: Form = {
  reference: "",
  importer: "Meridian Power Systems Pvt Ltd",
  exporter: "Shenzhen VoltEdge Technologies Co., Ltd",
  origin: "China",
  destination: "India",
  port: "Chennai Port (INMAA)",
  carrier: "Maersk Line",
  container_number: "MSKU7294816",
  product_description: "Lithium-ion battery packs, 48V 100Ah, for energy storage systems",
};

const NEXT = [
  { icon: FileUp, title: "Upload three documents", text: "Commercial invoice, packing list and bill of lading." },
  { icon: Brain, title: "AI reads and cross-checks", text: "Fields are extracted and compared across documents." },
  { icon: UserCheck, title: "You review and approve", text: "HS code, compliance and risk wait for your decision." },
];

export default function NewShipmentPage() {
  const router = useRouter();
  const toast = useToast();
  const [form, setForm] = useState<Form>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof Form, string>>>({});
  const [busy, setBusy] = useState(false);
  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    (Object.keys(EMPTY) as (keyof Form)[]).forEach((k) => {
      if (k !== "reference" && form[k].trim().length < (k === "container_number" ? 4 : 2)) next[k] = "Required";
    });
    setErrors(next);
    if (Object.keys(next).length) return toast("Complete the highlighted fields to continue.", "error");
    setBusy(true);
    try {
      const created = await api.createShipment({ ...form, reference: form.reference.trim() });
      toast(`Shipment ${created.reference} created.`, "success");
      router.push(`/shipments/${created.id}`);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not create the shipment.", "error");
      setBusy(false);
    }
  }

  const input = (k: keyof Form, label: string, placeholder: string, hint?: string) => (
    <Field label={label} error={errors[k]} hint={hint}>
      <input className={`field-input ${errors[k] ? "!border-signal-red !ring-signal-red/10" : ""}`} placeholder={placeholder} value={form[k]} onChange={set(k)} />
    </Field>
  );

  return (
    <div className="space-y-6">
      <div>
        <Link href="/shipments" className="text-sm font-semibold text-port hover:text-port-600">Shipments</Link>
        <h1 className="mt-1 font-display text-3xl font-extrabold text-prussian">Create shipment</h1>
        <p className="mt-1 text-ink-soft">Start with the basics. You will add documents next and the copilot will do the rest.</p>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[1.7fr_1fr]">
        <motion.form onSubmit={onSubmit} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="surface space-y-9 p-7" noValidate>
          <section>
            <h2 className="text-base font-bold text-ink">Shipment and parties</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {input("reference", "Shipment ID", "Leave blank to generate", "Optional. We assign one if empty.")}
              <span className="hidden sm:block" />
              {input("importer", "Importer", "Company receiving the goods")}
              {input("exporter", "Exporter", "Company sending the goods")}
            </div>
          </section>
          <section>
            <h2 className="text-base font-bold text-ink">Route</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {input("origin", "Origin country", "e.g. China")}
              {input("destination", "Destination country", "e.g. India")}
              {input("port", "Port of discharge", "e.g. Chennai Port (INMAA)")}
              {input("carrier", "Carrier", "e.g. Maersk Line")}
              {input("container_number", "Container number", "e.g. MSKU7294816")}
            </div>
          </section>
          <section>
            <h2 className="text-base font-bold text-ink">Cargo</h2>
            <div className="mt-4">
              <Field label="Product description" error={errors.product_description} hint="Include material, function and any model details. This improves HS code accuracy.">
                <textarea rows={3} className={`field-input resize-none ${errors.product_description ? "!border-signal-red" : ""}`} placeholder="What is being shipped?" value={form.product_description} onChange={set("product_description")} />
              </Field>
            </div>
          </section>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-alice-200 pt-6">
            <Link href="/dashboard" className="text-sm font-semibold text-ink-soft hover:text-ink">Cancel</Link>
            <Button type="submit" size="lg" loading={busy}>Create and add documents <ArrowRight className="h-4 w-4" /></Button>
          </div>
        </motion.form>

        <div className="space-y-5 xl:sticky xl:top-8">
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-prussian via-prussian-700 to-port p-6 text-white shadow-lift">
            <div className="absolute -right-10 -top-10 h-44 w-44 rounded-full bg-white/15 blur-3xl animate-aurora" />
            <Sparkles className="relative h-6 w-6 text-port-200" />
            <h3 className="relative mt-3 font-display text-lg font-bold">Try it with a ready example</h3>
            <p className="relative mt-1.5 text-sm leading-relaxed text-white/75">Fills in a lithium-ion battery shipment that matches the sample documents you can use on the next step.</p>
            <Button variant="light" size="sm" className="relative mt-4" onClick={() => { setForm(DEMO); setErrors({}); toast("Demo shipment loaded.", "info"); }}>Load demo shipment</Button>
          </div>
          <Card className="p-6">
            <h3 className="text-base font-bold text-ink">What happens next</h3>
            <ol className="mt-4 space-y-4">
              {NEXT.map((n) => (
                <li key={n.title} className="flex gap-3.5">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-port-50 text-port"><n.icon className="h-[18px] w-[18px]" /></span>
                  <div><p className="text-sm font-semibold text-ink">{n.title}</p><p className="text-[13px] leading-snug text-ink-soft">{n.text}</p></div>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </div>
  );
}
