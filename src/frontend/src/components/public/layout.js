import Footer from "./footer";
import Navigation from "./navigation";

function PublicLayout({ children, context }) {
  return (
    <div className="react-shell bg-light min-vh-100">
      <Navigation context={context} />
      <main className="react-shell__content">{children}</main>
      <Footer />
    </div>
  );
}

export default PublicLayout;
