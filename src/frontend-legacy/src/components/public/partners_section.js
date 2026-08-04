import { staticAsset } from "../../libs/static";

const PARTNERS = [
  {
    name: "Université de Genève",
    imagePath: "images/partners/ug.png",
    url: "https://unige.ch/",
  },
  {
    name: "The Graph Network",
    imagePath: "images/partners/tgn.png",
    url: "https://thegraphnetwork.org/",
  },
  {
    name: "HUG",
    imagePath: "images/partners/hug2.png",
    url: "https://www.hug.ch/",
  },
  {
    name: "Open Science Labs",
    imagePath: "images/partners/osl.png",
    url: "https://www.opensciencelabs.org/",
  },
];

function PartnersSection() {
  return (
    <div className="container-fluid px-4 py-5 my-5">
      <h2 className="pb-2 border-bottom text-center">Partners</h2>
      <h3 className="text-center mb-5">We are part of a great community</h3>
      <div className="col-10 col-xl-8 mx-auto">
        <div className="row row-cols-1 row-cols-md-2 row-cols-lg-4 g-4 py-2">
          {PARTNERS.map((partner) => (
            <div className="col my-2" key={partner.name}>
              <a href={partner.url} rel="noreferrer" target="_blank">
                <div className="py-5 d-grid align-items-center h-100 overflow-hidden rounded-4 border bg-white shadow-sm react-shell__partner-card">
                  <img
                    alt={partner.name}
                    className="mx-auto react-shell__partner-logo"
                    src={staticAsset(partner.imagePath)}
                  />
                </div>
              </a>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default PartnersSection;
