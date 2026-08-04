import PartnersSection from "../../components/public/partners_section";
import { staticAsset } from "../../libs/static";

const TEAM_MEMBERS = [
  {
    name: "Aziza Merzouki",
    role: "Co-founder & CEO",
    imagePath: "images/team/aziza.jpeg",
  },
  {
    name: "Erol Orel",
    role: "Co-founder & CPO",
    imagePath: "images/team/erol.jpeg",
  },
  {
    name: "Olivia Keiser",
    role: "Chairman",
    imagePath: "images/team/olivia.jpeg",
  },
  {
    name: "Ivan Osagawara",
    role: "Lead Developer",
    imagePath: "images/team/ivan.jpeg",
  },
  {
    name: "Sandro Loch",
    role: "DevOps Engineer",
    imagePath: "images/team/sandro.jpeg",
  },
  {
    name: "John Ever Vino Duran",
    role: "Full-Stack Developer",
    imagePath: "images/team/ever.jpeg",
  },
  {
    name: "Mia Müller",
    role: "Head of Marketing",
    imagePath: "images/team/mia.png",
  },
];

function Team() {
  return (
    <>
      <div className="d-flex justify-content-center align-items-center color-b react-shell__hero">
        <div className="container-md text-center">
          <span className="text-light logo-literev mb-4 d-block">
            Lite<span className="text-primary">Rev</span>
          </span>
          <div className="text-center text-light fs-2 fs-sm-3 fs-md-1 mt-5">
            <h1 className="mb-4 d-block display-4 lh-1">
              Meet the team behind LiteRev Legal.
            </h1>
          </div>
        </div>
      </div>

      <div className="container py-5 react-shell__team-section">
        <h2 className="display-5 fw-bold text-center">Meet the Team</h2>

        <div className="row justify-content-center align-items-center g-4 mb-5 pt-5">
          <div className="col-md-8 d-flex flex-column align-items-center">
            <img
              alt="LiteRev co-founders"
              className="img-fluid mb-3 react-shell__cofounders-image"
              src={staticAsset("images/team/co_founders.jpeg")}
            />
            <h5 className="text-center mt-3">Co-Founders</h5>
            <p className="text-muted text-center">CEO, CPO, and Chairman</p>
          </div>
        </div>

        <div className="row justify-content-center g-4 mb-5">
          {TEAM_MEMBERS.map((member) => (
            <div className="col-md-4 text-center" key={member.name}>
              <div className="card border-0 shadow-sm h-100 p-3">
                <img
                  alt={member.name}
                  className="card-img-top mx-auto mb-3 react-shell__team-image"
                  src={staticAsset(member.imagePath)}
                />
                <div className="card-body">
                  <h5>{member.name}</h5>
                  <p className="text-muted mb-0">{member.role}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <h3 className="text-center mb-4 pt-5">With the participation of</h3>
      </div>

      <PartnersSection />
    </>
  );
}

export default Team;
