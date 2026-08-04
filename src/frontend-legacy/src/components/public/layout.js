import Footer from "./footer";
import Navigation from "./navigation";
import Sidebar from "./sidebar";

const MESSAGE_VARIANTS = [
  "success",
  "danger",
  "warning",
  "info",
  "primary",
  "secondary",
];

function messageAlertClass(message) {
  const tags = `${message?.levelTag ?? ""} ${message?.tags ?? ""}`.split(/\s+/);
  const variant = MESSAGE_VARIANTS.find((candidate) =>
    tags.includes(candidate)
  );

  return `alert alert-${variant ?? "info"} mb-3`;
}

function DjangoMessages({ messages = [] }) {
  if (!messages.length) {
    return null;
  }

  return (
    <div className="container pt-4">
      {messages.map((message, index) => (
        <div
          className={messageAlertClass(message)}
          key={`${message.message}-${index}`}
          role="alert"
        >
          {message.message}
        </div>
      ))}
    </div>
  );
}

function PublicLayout({ children, context }) {
  return (
    <div className="react-shell bg-light min-vh-100">
      <Navigation context={context} />
      <div className="react-shell__body">
        <Sidebar context={context} />
        <div className="react-shell__main-column">
          <main className="react-shell__content">
            <DjangoMessages messages={context.messages} />
            {children}
          </main>
          <Footer />
        </div>
      </div>
    </div>
  );
}

export default PublicLayout;
