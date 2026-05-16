import Footer from "./footer";
import Navigation from "./navigation";
import Sidebar from "./sidebar";

function PublicLayout({ children, context }) {
  return (
    <div className="react-shell bg-light min-vh-100">
      <Navigation context={context} />
      <div className="react-shell__body">
        <Sidebar context={context} />
        <div className="react-shell__main-column">
          <main className="react-shell__content">{children}</main>
          <Footer />
        </div>
      </div>
    </div>
  );
}

export default PublicLayout;
