/**
 * Renders the server-generated floor-plan SVG (ai/visualization/floorplan.py)
 * directly — safe because the backend HTML-escapes every label it embeds
 * (catalog item names, all from our own seeded data, never raw user text)
 * before building the SVG string. This is the one visualization guaranteed
 * to be available regardless of any generative-image provider's status
 * (decisions D001/D003).
 */
export function FloorPlanView({ svg }: { svg: string }) {
  return <div className="floorplan-view" dangerouslySetInnerHTML={{ __html: svg }} />;
}
