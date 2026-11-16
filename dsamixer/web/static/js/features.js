// Display preferences only; the planner keeps using the saved time budgets.
let estimatesAndGoals = false;

export const showTimePlanning = () => estimatesAndGoals;
export function setFeatureConfig(config) {
  estimatesAndGoals = config.time_planning_enabled === true;
}
