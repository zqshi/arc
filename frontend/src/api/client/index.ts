import { API_BASE, ApiError, createRequestFn } from './base';
import type { ScanEvent } from './base';
import { createProjectMethods } from './projects';
import { createTodoMethods } from './todos';
import { createConversationMethods, createExperienceMethods } from './experiences';
import { createAgentMethods, createPlanningMethods } from './planning';
import { createSystemMethods } from './system';
import { createCapabilityMethods } from './capabilities';
import { createOrganizationMethods } from './organizations';
import { createTemplateMethods } from './templates';

const request = createRequestFn(API_BASE);

export const api = {
  ...createProjectMethods(request),
  ...createTodoMethods(request),
  ...createConversationMethods(request),
  ...createExperienceMethods(request),
  ...createAgentMethods(request),
  ...createPlanningMethods(request),
  ...createSystemMethods(request, API_BASE),
  ...createCapabilityMethods(request),
  ...createOrganizationMethods(request),
  ...createTemplateMethods(request),
};

export { ApiError };
export type { ScanEvent };
