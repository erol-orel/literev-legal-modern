import Footer from "./footer";
import Navigation from "./navigation";
import Sidebar from "./sidebar";

function PublicLayout({ children, context }) {
  return (
    <div className="react-shell bg-light min-vh-100">
      <Navigation context={context} />
      <div className="react-shell__body">
        <Sidebar context={context} />
        <main className="react-shell__content">{children}</main>
      </div>
      <Footer />
    </div>
  );
}

export default PublicLayout;
