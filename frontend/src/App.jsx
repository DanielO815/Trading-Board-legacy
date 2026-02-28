/**
 * Root-Komponente der Applikation.
 * 
 * Rendert Seitenkopf und lädt Haupt-Demo-Komponente ChartDemo.
 * 
 * @returns {JSX.Element} App-Layout mit Header und Chart-Ansicht
 */

import ChartDemo from "./ChartDemo.jsx";

export default function App() {
  return (
    <>
      <header className="page-header">
        <h1 className="page-title">Crypto Trading Board</h1>
      </header>

      <main className="main">
        <ChartDemo />
      </main>
    </>
  );
}
