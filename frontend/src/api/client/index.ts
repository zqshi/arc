import { API_BASE, ApiError, createRequestFn } from './base';
import type { ScanEvent } from './base';
import { createProjectMethods } from './projects';
import { createTodoMethods } from './todos';
import { createConversationMethods, createExperienceMethods } from './experiences';
import { createAgentMethods, createPlanningMethods } from './planning';
import { createSystemMethods } from './system';

const request = createRequestFn(API_BASE);

export const api = {
  ...createProjectMethods(request),
  ...createTodoMethods(request),
  ...createConversationMethods(request),
  ...createExperienceMethods(request),
  ...createAgentMethods(request),
  ...createPlanningMethods(request),
  ...createSystemMethods(request, API_BASE),
};

export { ApiError };
export type { ScanEvent };
